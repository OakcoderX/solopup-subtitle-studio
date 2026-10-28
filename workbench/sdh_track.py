from fractions import Fraction
"""Compose a reviewable SDH draft without treating model decisions as approval."""
import copy
from presentation import stabilize
from sound_readability import improve,music_onsets,sustained_onsets,repair_minimum_frames


def compose(state, candidates, decisions, shot_changes=None):
    out = copy.deepcopy(state)
    track = out.setdefault('sdh', copy.deepcopy(out.get('standard', [])))
    for i, row in enumerate(candidates, 1):
        key = str(i)
        decision = decisions.get(key, {})
        status = decision.get('status', '')
        owned = [c for c in track if c.get('sourceSoundId') == key or
                 (c.get('id') == f'S{i:03d}' and c.get('sourceDecision') is not None)]
        if status not in {'KEEP', 'REVISE'}:
            track[:] = [c for c in track if c not in owned]
            continue
        caption = (decision.get('caption') or row.get('caption', '')).strip()
        if not caption:
            raise ValueError('Sound caption cannot be empty')
        # Re-entering review must not overwrite a subtitle edit or its timing.
        if len(owned) == 1 and owned[0].get('sourceDecision') == decision:
            continue
        track[:] = [c for c in track if c not in owned]
        human = decision.get('reviewer') == 'human' and decision.get('humanApproved') is True
        cue = {'id': f'S{i:03d}', 'sourceSoundId': key, 'kind': 'sound',
               'start': float(row['start']), 'end': float(row['end']),
               'text': caption, 'checked': human, 'sourceDecision': copy.deepcopy(decision)}
        semantic=decision.get('semanticReview',{})
        machine_resolved=(semantic.get('status')=='machine_reviewed' and decision.get('uncertain') is False
                          and semantic.get('caption')==caption and semantic.get('decision')==status
                          and semantic.get('start')==float(row['start']) and semantic.get('end')==float(row['end'])
                          and bool(semantic.get('audioEvidence')) and bool(semantic.get('pictureEvidence'))
                          and len(set(semantic.get('evidence',[])))>=2)
        from evidence_gate import evidence_flags
        probe=dict(cue,semanticReview=semantic)
        machine_resolved=machine_resolved and not evidence_flags(probe)
        if not human and not machine_resolved:
            cue['unresolved'] = 'SDH 系统建议，待视听确认。'
        elif machine_resolved and not human:
            cue['semanticReview']=copy.deepcopy(semantic)
            cue['reviewState']='machine_reviewed_not_human_approved'
        track.append(cue)
    track.sort(key=lambda c: (float(c['start']), float(c['end'])))
    fps=float(Fraction(str(state.get('frameRate',24))))
    track=music_onsets(track,fps)
    track=sustained_onsets(track,fps)
    track=improve(track,shot_changes,fps)
    out['sdh']=track=stabilize(track,shot_changes)
    from display_timing import optimize
    out['sdh']=track=optimize(track,shot_changes,float(Fraction(str(state.get('frameRate',24)))))
    out['sdh']=track=repair_minimum_frames(track,shot_changes,fps)
    threshold=float(state.get('reviewPolicy',{}).get('removeSoundBelowSeconds',0))
    from timed_text import frame
    removed=[c for c in track if c.get('kind')=='sound' and (frame(c['end'],fps)-frame(c['start'],fps))/fps<threshold]
    if removed:
        out.setdefault('soundDisplayOmissions',[]).extend({'id':c['id'],'start':c['start'],'end':c['end'],'text':c['text'],'reason':'User project minimum readable SDH exposure', 'threshold':threshold} for c in removed)
        out['soundDisplayOmissions']=list({x['id']:x for x in out['soundDisplayOmissions']}.values())
        out['sdh']=track=[c for c in track if c not in removed]
    # Lay out against actual visible labels, not the full acoustic event duration.
    # SDH-specific splits must not fragment the separate standard-English track.
    from layout_policy import fit_sound_dialogue
    speech=[c for c in track if c.get('kind')!='sound']
    sound=[c for c in track if c.get('kind')=='sound']
    speech,splits=fit_sound_dialogue(speech,[(c['start'],c['end']) for c in sound],float(Fraction(str(state.get('frameRate',24)))))
    out['sdh']=track=sorted(speech+sound,key=lambda c:(c['start'],c['end']))
    out['sdhLayoutSplits']=splits
    pending = sum(decisions.get(str(i), {}).get('status') not in {'KEEP', 'REVISE', 'REMOVE'}
                  for i in range(1, len(candidates)+1))
    out['sdhComposition'] = {'mode': 'review_draft', 'included': sum('sourceSoundId' in c for c in track),
                             'pending': pending, 'total': len(candidates)}
    release = out.setdefault('release', {})
    release['content_verified'] = False
    # Replace the obsolete all-or-nothing notice, retaining unrelated blockers.
    release['blockers'] = [b.replace('声音建议尚未合并进SDH。', '') for b in release.get('blockers', [])]
    notice = 'SDH 草稿已包含建议保留/修改的声音；未决候选未合入，系统建议不等于人工批准。'
    if notice not in release['blockers']:
        release['blockers'].append(notice)
    from layout_policy import prepare
    return prepare(out)
