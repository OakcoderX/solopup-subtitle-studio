"""Explicit, project-scoped name-merge guard without built-in character data."""
import re
from itertools import permutations
def merged_protected_names(before,after,names):
    names=[n for n in names if isinstance(n,str) and n.strip()]
    for a,b in permutations(names,2):
        if re.search(r'(?<!\w)'+re.escape(a)+r'(?!\w)',before,re.I) and re.search(r'(?<!\w)'+re.escape(b)+r'(?!\w)',before,re.I):
            if re.search(r'(?<!\w)'+re.escape(a+b)+r'(?!\w)',after,re.I):return True
    return False
