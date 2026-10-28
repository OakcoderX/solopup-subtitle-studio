"""Deterministic SDH format and simultaneous-display checks; never invent content."""
import re
from presentation import layout_parts

def style_issues(c):
    text=re.sub(r'<[^>]*>','',c['text']);flags=[]
    if c.get('kind')=='sound':
        if not re.fullmatch(r'\[[^\[\]\n]+\]',text):flags.append('sound_brackets')
        if c.get('italic'):flags.append('sound_italic')
        if re.search(r'character vocalization|[\"“”]',text,re.I):flags.append('sound_wording_review')
        if len(text.strip('[]').split())>5:flags.append('sound_verbose_review')
        if re.search(r'\b[A-Z]{2,}\b',text):flags.append('sound_all_caps')
        if re.fullmatch(r'\[(?:sound|noise|sound effect|sounds)\]',text,re.I):flags.append('sound_vague')
        # Amazon EP14 QC rejects cues that narrate visible actions. Describe
        # the audible result instead of what a character looks like or does.
        visual_action=(r'\b(?:winks?|smiles?|realiz(?:es|ing)|present(?:s|ing)|hands?|'
                       r'snatches?|pretends?|gestures?|points?|nods?|waves?|'
                       r'looks?\s+(?:like|at)|express(?:es|ing)|approaches|turns?\s+to)\b')
        if re.search(visual_action,text.strip('[]'),re.I):flags.append('sound_visual_action')
    p=c.get('presentation')
    if p in {'voiceover','device','song'} and not c.get('italic'):flags.append('italic_required')
    if p=='onscreen' and c.get('italic') and not c.get('italicReason'):flags.append('italic_unexplained')
    if p=='unknown':flags.append('presentation_unresolved')
    if c.get('kind')=='song':
        if not c.get('italic'):flags.append('italic_required')
        if not c.get('songEnding') in {'fade','interrupted'} and not re.fullmatch(r'(?:\[[^\]]+\]\s*)?♪ .+ ♪♪?',text,re.S):flags.append('song_markers')
        if re.search(r'\.\s*♪',text):flags.append('song_final_period')
        if re.search(r',\s+[A-Z][a-z]',text):flags.append('song_case_after_comma')
    if c.get('kind')=='speech':
        # Check source sentence punctuation, not artificial line fragments
        # created by the layout engine. Lyric punctuation follows the song
        # master and is checked by its dedicated rules above.
        body=str(c.get('sourceText') or text).strip()
        # Amazon EP14 QC repeatedly cited missing terminal punctuation and
        # unreviewed continuation marks. Flag for contextual correction; do
        # not invent punctuation or rewrite the spoken words automatically.
        if re.search(r'[A-Za-z0-9]["”’)]?$',body):flags.append('terminal_punctuation_review')
        elif re.search(r'(?:\.\.\.|…|[-—])$',body):flags.append('continuation_punctuation_review')
    if '  ' in text:flags.append('double_space')
    return list(dict.fromkeys(flags))

def screen_issues(rows,frame,rate):
    """Sweep all visible intervals, not only the preceding row's end."""
    out=[];bounds=sorted({frame(c[k],rate) for c in rows for k in ['start','end']})
    seen=set()
    for a,b in zip(bounds,bounds[1:]):
        active=[c for c in rows if frame(c['start'],rate)<=a<frame(c['end'],rate)]
        if len(active)<2:continue
        ids=tuple(c.get('id') for c in active)
        if ids in seen:continue
        seen.add(ids)
        lines=len(layout_parts(active))
        flags=[]
        if sum(c.get('kind')!='sound' for c in active)>1:flags.append('simultaneous_dialogue_overlap')
        if sum(c.get('kind')=='sound' for c in active)>1:flags.append('sound_density_review')
        if lines>2:
            exception=lines==3 and any(c.get('kind')=='sound' or '[' in c['text'] for c in active) and all(c.get('thirdLineApproved') for c in active)
            if not exception:flags.append('simultaneous_line_limit')
        if len({c.get('region','bottom') for c in active})>1:flags.append('simultaneous_regions_review')
        # Both incoming labels are a real reading load, even when individually below limits.
        chars=sum(len(c['text'].replace('\n',' ')) for c in active)
        if chars>84 and not all(c.get('thirdLineApproved') for c in active):flags.append('simultaneous_text_load')
        if flags:out.append({'id':'+'.join(map(str,ids)),'cue_ids':list(ids),'start':active[0]['start'],'end':max(c['end'] for c in active),'text':'\n'.join(c['text'] for c in active),'flags':flags,'blocking_flags':flags})
    from presentation import visible_events
    for a,b,g in visible_events(rows,frame,rate):
        if (b-a)/float(__import__("fractions").Fraction(str(rate)))>7+1e-6:
            out.append({'id':'+'.join(str(c.get('id')) for c in g),'text':'\n'.join(c['text'] for c in g),'flags':['composite_duration_long'],'blocking_flags':['composite_duration_long']})
        if b-a<20:
            out.append({'id':'+'.join(str(c.get('id')) for c in g),'start':a/float(__import__("fractions").Fraction(str(rate))),'end':b/float(__import__("fractions").Fraction(str(rate))),'text':'\n'.join(c['text'] for c in g),'flags':['export_event_short'],'blocking_flags':['export_event_short']})
    from presentation import position_changes
    for item in position_changes(rows,frame,rate):
        out.append({'id':'+'.join(item['cue_ids']),'cue_ids':item['cue_ids'],
                    'start':item['time'],'text':'Persistent subtitle changes line position',
                    'flags':['vertical_position_jump'],'blocking_flags':[]})
    return out
