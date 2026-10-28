"""Evidence validity checks shared by editing, composition, QA and final export.
These checks detect missing/stale evidence; they cannot establish audible truth.
"""
import hashlib
import json
import math

VERSION = 'public-evidence-v1'
SOUND_PROMPT = 'Compare the original audio and picture. Transcribe intelligible speech regardless of the visible species or character. A screenplay parenthetical or a visible action is not proof that words or a sound occurred. Distinguish speech, vocalizations and meaningful effects. Never invent words, speaker identity, sound sources or phonetic syllable counts. Keep ambiguous cases uncertain. Add SDH sound descriptions only when omission loses story, emotional or comprehension information not already clear from dialogue and picture. Use title-specific behavior references only when explicitly supplied and supported by the original audio. Machine evidence does not create human approval.'

def signature(c):
    fields = {k:c.get(k) for k in ('text','start','end','kind','region','italic','presentation')}
    return hashlib.sha256(json.dumps(fields,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def evidence_flags(c):
    flags=[]
    e=c.get('semanticReview') or c.get('sourceDecision',{}).get('semanticReview') or {}
    if e.get('status')=='machine_reviewed':
        if not e.get('audioEvidence') or len(set(e.get('evidence',[])))<2:
            flags.append('semantic_evidence_incomplete')
        if e.get('uncertain') or e.get('conflict') or c.get('crossModalConflicts'):
            flags.append('semantic_evidence_conflict')
        # Compare original acoustic anchors, not a deliberately shortened display tail.
        start=c.get('soundAudioStart',c['start'])
        end=c.get('soundAudioEnd',c.get('soundOriginalEnd',c['end']))
        if e.get('caption')!=c['text'] or e.get('start')!=start or e.get('end')!=end:
            flags.append('semantic_evidence_stale')
        clip=e.get('clip')
        if clip is not None:
            try:
                a,b=map(float,clip)
                valid=all(math.isfinite(x) for x in (a,b,start,end)) and a<=start<end<=b
            except (TypeError,ValueError):valid=False
            if not valid:flags.append('evidence_outside_clip')
        decision=c.get('sourceDecision',{})
        if not (e.get('narrativeValue') or decision.get('narrativeValue')):
            flags.append('sound_necessity_unverified')
        if e.get('visualOnly') is True:flags.append('sound_inferred_from_picture')
    binding=c.get('reviewBinding')
    if binding and binding!=signature(c):flags.append('review_evidence_stale')
    if c.get('reviewInvalidated') and not c.get('checked'):flags.append('review_evidence_stale')
    return list(dict.fromkeys(flags))

def refresh(state):
    """Bind legacy reviews on first preparation; thereafter edits invalidate locally.
    Never creates checked/approved states or clears prior uncertainty.
    """
    tasks=[]
    for track in ('standard','sdh'):
        for c in state.get(track,[]):
            flags=evidence_flags(c)
            if flags:
                c['checked']=False
                c['reviewInvalidated']=True
                if c.get('speedReview'):
                    c['speedReview'].update(accepted=False,invalidated=True)
                state.setdefault('release',{})['content_verified']=False
                tasks.append({'track':track,'id':c.get('id'),'start':c['start'],
                              'cue_ids':[c.get('id')],'action':'review_evidence','reasons':flags})
            if c.get('checked') or c.get('reviewBinding') or c.get('semanticReview'):
                c['reviewBinding']=signature(c)
    state['evidenceTasks']=tasks
    return state


def reconcile_edit(old, new):
    """Server-owned invalidation: clients cannot drop provenance to clear a gate."""
    for track in ('standard','sdh'):
        prior={c.get('id'):c for c in old.get(track,[])}
        for c in new.get(track,[]):
            previous=prior.get(c.get('id'))
            if not previous:continue
            for key in ('semanticReview','sourceDecision','crossModalConflicts','reviewBinding','reviewInvalidated','soundAudioStart','soundAudioEnd','soundOriginalEnd'):
                if key in previous:c[key]=previous[key]
            if signature(previous)!=signature(c):
                c['checked']=False
                c['reviewInvalidated']=True
                c['reviewBinding']=signature(c)
                if c.get('speedReview'):c['speedReview'].update(accepted=False,invalidated=True)
                new.setdefault('release',{})['content_verified']=False
    return new
