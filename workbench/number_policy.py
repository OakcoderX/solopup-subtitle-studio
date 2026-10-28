"""Conservative English number formatting; source transcript stays untouched."""
import copy,re
from fidelity import number_value
TOKENS='zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety hundred and'.split()
PAT=re.compile(r"\b(?:"+'|'.join(TOKENS)+r")\b(?:[ -]+(?:"+'|'.join(TOKENS)+r")\b)*",re.I)
UNIT=re.compile(r'^\s+(?:grams?|kilograms?|milliliters?|millilitres?|liters?|litres?|minutes?|seconds?|degrees?)\b',re.I)
def candidates(rows):
    previous=None
    for c in sorted(rows,key=lambda x:(x['start'],x['end'])):
        if c.get('kind')=='sound':continue
        text=' '.join(c['text'].split())
        for m in PAT.finditer(text):
            raw=m.group();leading=re.match(r'^and\s+',raw,re.I);raw=raw[leading.end():] if leading else raw;value=number_value(re.findall(r'[a-z]+',raw.lower()))
            if value is None or value<11 or not UNIT.match(text[m.end():]):continue
            prefix=text[:m.start()].strip()
            continuation=bool(previous and c['start']-previous['end']<=10 and previous['text'].rstrip().endswith((',',':')))
            safe=(bool(prefix) and not re.search(r'[.!?]\s*$',prefix)) or (not prefix and continuation)
            if safe:yield c,raw,str(value)
        previous=c

def normalize(rows):
    out=copy.deepcopy(rows)
    from layout_policy import invalidate,wrap
    for c,old,new in list(candidates(out)):
        text=' '.join(c['text'].split());c['text']=wrap(text.replace(old,new,1))
        c.setdefault('numberFormatting',[]).append({'from':old,'to':new,'rule':'AMZ-NUM-01: quantity in sentence/list continuation','reviewer':'system'})
        invalidate(c)
    return out

def issues(rows):
    return [{'id':c.get('id'),'start':c['start'],'end':c['end'],'text':c['text'],
      'flags':['number_format'],'blocking_flags':['number_format'],'suggestion':old+' → '+new} for c,old,new in candidates(rows)]
