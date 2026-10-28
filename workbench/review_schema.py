"""Normalize explicit per-cue verdicts without inventing model decisions."""
import copy
def normalize_adjudications(parsed,cue_ids,sound_aliases=None):
 # Some responses put typed per-ID verdicts in speech rather than cue_reviews.
 # Move only requested, explicitly adjudicated rows; never invent an answer.
 out=copy.deepcopy(parsed);existing={str(v.get('id')) for v in out.get('cue_reviews',[])};moved=[];speech=[]
 for row in out.get('speech',[]):
  rid=str(row.get('id'))
  if rid in cue_ids and rid not in existing and row.get('verdict') in {'agree','correct','nonlexical','uncertain'}:
   out.setdefault('cue_reviews',[]).append(row);existing.add(rid);moved.append(rid)
  else:speech.append(row)
 out['speech']=speech
 for row in out.get('cue_reviews',[]):
  if not row.get('audio_evidence') and row.get('specific_audio_evidence'):row['audio_evidence']=row['specific_audio_evidence']
 if moved:out['_schema_normalization']={'moved_explicit_verdict_ids':moved,'decisions_unchanged':True}
 for row in out.get('sound_reviews',[]):
  original=str(row.get('id'));mapped=(sound_aliases or {}).get(original)
  if mapped and mapped!=original:row['id']=mapped;row['returned_cue_id']=original
 return out
