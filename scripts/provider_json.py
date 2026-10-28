"""Read one provider JSON object; allow only a labeled explanatory suffix."""
import json,re

def parse_object(raw):
    value=re.sub(r'^```(?:json)?\s*|\s*```$','',raw.strip())
    value=re.sub(r'("confidence"\s*:\s*)(high|medium|low)(\s*[,}])',r'\1"\2"\3',value)
    repairs=0
    try:obj,end=json.JSONDecoder().raw_decode(value)
    except json.JSONDecodeError:
        # Known provider shape: a row closes before its two adjudication
        # fields, then closes a second time. Remove only that extra brace;
        # never alter strings, words, IDs, decisions or uncertainty values.
        repaired,repairs=re.subn(r'},(\s*"resolves_prior_disagreement"\s*:)',r',\1',value)
        if not repairs:raise
        obj,end=json.JSONDecoder().raw_decode(repaired);value=repaired
    if not isinstance(obj,dict):raise ValueError('Expected one JSON object')
    suffix=value[end:].strip()
    if suffix.startswith('```'):suffix=suffix[3:].strip()
    if suffix and not suffix.startswith(('Reasoning summary:','Reasoning:')):raise ValueError('Unexpected trailing provider content')
    if suffix and re.search(r'[\[{]',suffix):raise ValueError('Ambiguous additional structured content')
    if repairs:obj['_provider_json_repair']={'kind':'extra_row_brace_before_adjudication_fields','count':repairs,'caption_strings_unchanged':True}
    return obj
