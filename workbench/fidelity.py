"""Check lexical fidelity independently of layout and reading speed.

sourceText is the adjudicated audio transcript, never a screenplay quotation.
Split cues share sourceGroup and the same complete sourceText. Formatting may
change; replacing or dropping words requires an explicit unresolved edit.
"""
import difflib
import re


def words(text):
    text = re.sub(r"\[[^\]]*\]", "", str(text)).replace("’", "'")
    return re.findall(r"[\w]+(?:'[\w]+)*", text.lower())


def number_value(tokens):
    """Strict English cardinal grammar, 0..999, for audited display changes."""
    units='zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split()
    tens={'twenty':20,'thirty':30,'forty':40,'fifty':50,'sixty':60,'seventy':70,'eighty':80,'ninety':90}
    if len(tokens)==1 and tokens[0] in units:return units.index(tokens[0])
    if tokens and tokens[0] in tens:
        if len(tokens)==1:return tens[tokens[0]]
        if len(tokens)==2 and tokens[1] in units[1:10]:return tens[tokens[0]]+units.index(tokens[1])
    if len(tokens)>=2 and tokens[0] in units[1:10] and tokens[1]=='hundred':
        rest=tokens[2:]
        if rest and rest[0]=='and':rest=rest[1:]
        if not rest and len(tokens)==2:return units.index(tokens[0])*100
        value=number_value(rest)
        if value is not None and 0<value<100:return units.index(tokens[0])*100+value
    return None


def formatted_source(source, items):
    # The original transcript remains immutable. Accept only explicit, equal-value
    # formatting records; a record cannot authorize arbitrary text replacement.
    result=list(source);seen=set();mappings=[]
    for _,cue in items:
        for edit in cue.get('numberFormatting',[]):
            old,new=words(edit.get('from','')),str(edit.get('to',''))
            key=(tuple(old),new)
            if key in seen:continue
            seen.add(key)
            if not re.fullmatch(r'[0-9]+',new) or number_value(old)!=int(new):continue
            mappings.append((old,new))
    # Longest phrases first: fifty must not consume the suffix of two hundred fifty.
    for old,new in sorted(mappings,key=lambda x:len(x[0]),reverse=True):
        matches=[i for i in range(len(result)-len(old)+1) if result[i:i+len(old)]==old]
        for i in reversed(matches):result[i:i+len(old)]=[new]
    return result

def audit(rows, expected=None):
    groups = {}
    for index, cue in enumerate(rows, 1):
        if "sourceText" not in cue:
            if not re.fullmatch(r"\s*\[[^\]]+\]\s*", cue.get("text", "")):
                groups.setdefault("missing:" + str(index), []).append((index, cue))
            continue
        if not cue["sourceText"]:
            continue
        groups.setdefault(cue.get("sourceGroup", cue.get("id", str(index))), []).append((index, cue))
    findings = []
    for group, items in groups.items():
        first_index, first = items[0]
        if "sourceText" not in first:
            findings.append({"cue": first_index, "id": first.get("id"), "group": group,
                             "flags": ["source_evidence_missing"], "text": first["text"]})
            continue
        transcript = first["sourceText"]
        actual = " ".join(c["text"] for _, c in items)
        source, target = formatted_source(words(transcript), items), formatted_source(words(actual), items)
        inconsistent = any(c["sourceText"] != transcript for _, c in items)
        if source == target and not inconsistent:
            continue
        changes = []
        for tag, a, b, x, y in difflib.SequenceMatcher(None, source, target, autojunk=False).get_opcodes():
            if tag != "equal":
                changes.append({"operation": tag, "source": " ".join(source[a:b]), "caption": " ".join(target[x:y])})
        findings.append({"cue": first_index, "id": first.get("id"), "group": group,
                         "start": first["start"], "end": items[-1][1]["end"],
                         "flags": ["source_group_conflict" if inconsistent else "lexical_change"],
                         "text": actual, "source": transcript, "changes": changes})
    for group, source in (expected or {}).items():
        if group not in groups:
            findings.append({"id": group, "group": group, "flags": ["source_group_missing"], "source": source, "text": ""})
        elif any(c.get("sourceText") != source for _, c in groups[group]):
            findings.append({"id": group, "group": group, "flags": ["source_baseline_changed"], "source": source, "text": ""})
    return findings
