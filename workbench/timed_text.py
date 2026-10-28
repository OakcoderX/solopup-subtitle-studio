"""Amazon project iTT writer and deterministic preflight; never certifies editorial accuracy."""
import math,re
from fidelity import audit as audit_fidelity
from sdh_validation import style_issues,screen_issues
from presentation import groups, visible_events, layout_parts
from fractions import Fraction
from xml.etree import ElementTree as E
TT='http://www.w3.org/ns/ttml';TTS=TT+'#styling';TTP=TT+'#parameter';XML='http://www.w3.org/XML/1998/namespace'
for prefix,uri in [('',TT),('tts',TTS),('ttp',TTP)]:E.register_namespace(prefix,uri)
PROFILE = {'id': 'amazon_itt_children_17_120', 'cps': 17, 'wpm': 120, 'review_threshold_cps': 17, 'max_lines': 2, 'max_line_chars': 42, 'min_frames': 20, 'max_seconds': 7, 'gap_frames': 2, 'font_family': 'sansSerif', 'font_size': '100%', 'color': 'white', 'source_hierarchy': ['title-specific delivery instructions', 'target-language style guide', 'general platform requirements', 'explicit project settings'], 'note': 'Archived English children profile: 17 CPS and 120 WPM. Confirm the recipient and title-specific rules; other project modes keep their own policy. A local check is not platform acceptance.'}

def rate_info(rate):
 r=Fraction(str(rate));nominal=round(float(r))
 if r not in [Fraction(x) for x in [24,25,30,48,50,60]]+[Fraction(24000,1001),Fraction(30000,1001),Fraction(60000,1001)]:raise ValueError('Unsupported or unverified frame rate')
 m=r/nominal;return r,nominal,f'{m.numerator} {m.denominator}'

def frame(t,rate):return int(math.floor(float(t)*float(Fraction(str(rate)))+.5))
def timecode(t,rate):
 _,fps,_=rate_info(rate);n=frame(t,rate);s,f=divmod(n,fps);m,s=divmod(s,60);h,m=divmod(m,60);return f'{h:02}:{m:02}:{s:02}:{f:02}'

def plain(text):return re.sub(r'<[^>]*>','',str(text))
def word_count(text):
 return len(re.findall(r"[A-Za-z0-9]+(?:['’\-][A-Za-z0-9]+)*",plain(text)))

def speed_accepted(c,rate='24',profile=None):
 profile=profile or PROFILE
 review=c.get('speedReview') or {}
 return (review.get('accepted') is True and review.get('reviewer')=='user' and review.get('policy')==profile['id']
         and review.get('text')==c['text'] and review.get('start')==c['start']
         and review.get('end')==c['end'] and review.get('fps')==float(Fraction(str(rate))))

def blocking_issues(issues):
 return [x for x in issues if x.get('blocking_flags',x['flags'])]

def unresolved_flags(cue):
    """Keep uncertainty blocking, but classify timing/sound/content separately.

    Legacy `unresolved` text carries several kinds of work. Treating every note
    as unresolved dialogue inflated content-error counts and hid what needs doing.
    Unknown notes remain conservative content blockers until explicitly mapped.
    """
    note=str(cue.get('unresolved') or '').strip()
    if not note:return []
    flags=[]
    if any(token in note for token in (
        '时间边界尚无逐词证据','独立逐词转写与 Qwen 估计的起点相差',
        'relative timing','时码仍待','时码待','时间边界','timing evidence',
        'time boundary','start-time disagreement','timecode remains','timing remains')):
        flags.append('timing_evidence_unresolved')
    if cue.get('kind')=='sound' and any(token in note for token in (
        'SDH 系统建议，待视听确认','sound suggestion pending audiovisual review')):
        flags.append('sound_review_required')
    if any(token in note for token in ('固定歌曲母版','song master timing','歌词母版时码')):
        flags.append('song_timing_unresolved')
    if any(token in note for token in (
        '听辨疑点','Targeted audio review remains uncertain','对白与声音复核不一致',
        '本轮音频复核仍不确定','script wording conflict','transcription uncertainty')):
        flags.append('unresolved_content')
    # If a compound legacy note states both timing uncertainty and a content
    # disagreement, preserve both blockers. A known category alone must not
    # accidentally erase a different kind of review work.
    if not flags:
        flags.append('unresolved_content')
    return list(dict.fromkeys(flags))

def check(rows,rate='24',duration=None,source_manifest=None,song_speed_advisory=False,preferred_spellings=None,profile=None):
 profile=profile or PROFILE
 cps_limit=profile['cps'];wpm_limit=profile['wpm']
 speed_flags={f'cps_over_{cps_limit}',f'wpm_over_{wpm_limit}'}
 r,_,_=rate_info(rate);issues=[];prev=None;prev_c=None
 for i,c in enumerate(rows,1):
  text=plain(c['text']);a=frame(c['start'],rate);b=frame(c['end'],rate);d=float(Fraction(b-a)/r);flags=[]
  if a<0 or b<=a or (duration is not None and b>frame(duration,rate)):flags.append('time_bounds')
  if b-a<20:flags.append('duration_short')
  if d>7+1e-6:flags.append('duration_long')
  lines=text.splitlines()
  if (len(lines)>2 and not (len(lines)==3 and c.get('thirdLineApproved') and '[' in text)) or any(len(l)>42 for l in lines):flags.append('line_limit')
  # A line break replaces a word space. Spaces and punctuation count.
  cps=len(' '.join(lines))/max(d,.00001)
  wpm=word_count(text)*60/max(d,.00001)
  if wpm>wpm_limit+1e-6:flags.append(f'wpm_over_{wpm_limit}')
  if cps>cps_limit+1e-6:flags.append(f'cps_over_{cps_limit}')
  if prev is not None and a-prev<2:
   intentional=a<prev and (c.get('kind')=='sound' or prev_c.get('kind')=='sound')
   if not intentional:flags.append('overlap' if a<prev else 'gap_under_2_frames')
  flags.extend(style_issues(c))
  from evidence_gate import evidence_flags
  flags.extend(evidence_flags(c))
  flags.extend(unresolved_flags(c))
  if c.get('region','bottom') not in {'top','bottom'}:flags.append('region')
  if flags:
   accepted=speed_accepted(c,rate,profile) and (cps>cps_limit+1e-6 or wpm>wpm_limit+1e-6)
   advisory=bool(song_speed_advisory and c.get('kind')=='song')
   blocking=[f for f in flags if not ((accepted or advisory) and f in speed_flags)]
   issues.append({'cue':i,'id':c.get('id'),'start':c['start'],'end':c['end'],'cps':round(cps,2),'wpm':round(wpm,2),'flags':flags,'text':text,
                  'speed_band':f'over_{cps_limit}' if cps>cps_limit+1e-6 else (f'over_{wpm_limit}_wpm' if wpm>wpm_limit+1e-6 else 'within_limits'),
                  'song_speed_advisory':advisory,'speed_accepted':accepted,'blocking_flags':blocking})
  prev=b;prev_c=c
 from number_policy import issues as number_issues
 spelling_issues=[]
 for cue_index,cue in enumerate(rows,1):
  for variant,preferred in (preferred_spellings or {}).items():
   match=re.search(r'(?<!\w)'+re.escape(str(variant))+r'(?!\w)',plain(cue['text']),re.I)
   if match and match.group()!=str(preferred):
    spelling_issues.append({'cue':cue_index,'id':cue.get('id'),'start':cue['start'],'end':cue['end'],
      'text':plain(cue['text']),'flags':['preferred_spelling'],'blocking_flags':['preferred_spelling'],
      'correction':preferred,'source':'Project terminology; verify against final audio'})
 return issues + spelling_issues + number_issues(rows) + screen_issues(rows,frame,rate) + audit_fidelity(rows,source_manifest)

def write_itt(rows,path,rate='24',language='en-US'):
 _,fps,mult=rate_info(rate)
 root=E.Element('{'+TT+'}tt',{'{'+XML+'}lang':language,'{'+TTP+'}timeBase':'smpte','{'+TTP+'}frameRate':str(fps),'{'+TTP+'}frameRateMultiplier':mult,'{'+TTP+'}dropMode':'nonDrop'})
 head=E.SubElement(root,'{'+TT+'}head');styling=E.SubElement(head,'{'+TT+'}styling')
 for name,italic in [('normal','normal'),('italic','italic')]:
  E.SubElement(styling,'{'+TT+'}style',{'{'+XML+'}id':name,**{'{'+TTS+'}'+k:v for k,v in {'fontFamily':'sansSerif','fontSize':'100%','fontWeight':'normal','fontStyle':italic,'color':'white'}.items()}})
 layout=E.SubElement(head,'{'+TT+'}layout')
 for name,y,align in [('top','0%','before'),('bottom','85%','after')]:
  E.SubElement(layout,'{'+TT+'}region',{'{'+XML+'}id':name,**{'{'+TTS+'}'+k:v for k,v in {'origin':f'0% {y}','extent':'100% 15%','textAlign':'center','displayAlign':align}.items()}})
 body=E.SubElement(root,'{'+TT+'}body',{'style':'normal'});div=E.SubElement(body,'{'+TT+'}div')
 def content(parent,c):
  text=plain(c['text'])
  if c.get('italic'):parent=E.SubElement(parent,'{'+TT+'}span',{'style':'italic'})
  for j,line in enumerate(text.split('\n')):
   if j:E.SubElement(parent,'{'+TT+'}br')
   for token in re.split(r'(\[[^\]]+\])',line):
    if not token:continue
    if token.startswith('[') and token.endswith(']'):E.SubElement(parent,'{'+TT+'}span',{'style':'normal'}).text=token
    elif len(parent):parent[-1].tail=(parent[-1].tail or '')+token
    else:parent.text=(parent.text or '')+token
 compiled=visible_events(rows,frame,rate)
 for i,(a,b,group) in enumerate(compiled,1):
  p=E.SubElement(div,'{'+TT+'}p',{'{'+XML+'}id':f'c{i:04d}','begin':timecode(Fraction(a)/Fraction(str(rate)),rate),'end':timecode(Fraction(b)/Fraction(str(rate)),rate),'region':group[0].get('region','bottom')})
  for j,line in enumerate(layout_parts(group)):
   if j:E.SubElement(p,'{'+TT+'}br')
   for c,text in line:
    span=E.SubElement(p,'{'+TT+'}span')
    content(span,{**c,'text':text})
 E.ElementTree(root).write(path,encoding='UTF-8',xml_declaration=True)
 # Independent parse/content roundtrip; this is not full schema verification.
 parsed=E.parse(path);out=[''.join(p.itertext()) for p in parsed.findall('.//{'+TT+'}p')]
 assert out==[''.join(plain(t) for line in layout_parts(g) for c,t in line) for _,_,g in compiled]
