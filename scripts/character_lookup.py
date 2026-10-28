"""Extract screenplay speaker labels to a compact Markdown glossary before ASR."""
import argparse, hashlib, re, zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

def script_text(path):
    path=Path(path)
    if path.suffix.lower()=='.docx':
        with zipfile.ZipFile(path) as z: root=ET.fromstring(z.read('word/document.xml'))
        ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        lines=[]
        for paragraph in root.findall('.//w:p',ns):
            parts=[]
            for run in paragraph.findall('.//w:r',ns):
                for node in run:
                    if node.tag.endswith('}tab'):parts.append('\t')
                    elif node.tag.endswith('}br'):parts.append('\n')
                    elif node.tag.endswith('}t'):parts.append(node.text or '')
            text=''.join(parts)
            # Right-tabbed trailing cue numbers are layout metadata, not quantities.
            # Never strip digits attached to a word without a real DOCX tab.
            text=re.sub(r'\t+\s*\d+\s*$', '', text)
            lines.append(text.replace('\t',' '))
        return '\n'.join(lines)
    return path.read_text(encoding='utf-8-sig')

def extract(path, output):
    output=Path(output)
    if output.exists() and '<!-- curated-series:' in output.read_text():
        # Preserve curated names; new screenplay labels remain review candidates.
        extract(path, output.with_name('character_candidates.md'))
        return output
    text=script_text(path); names={}
    for line in text.splitlines():
        label=re.sub(r'^\s*\d+|\d+\s*$', '',line.strip()).strip()
        label=re.sub(r'\([^)]*\)?','',label).strip()
        if not label or len(label)>65 or re.search(r'[.!?…–:]',label) or not re.fullmatch(r"[A-Z &,/’'\-]+",label): continue
        if any(w in label for w in ['EXT','INT','TRANSITION','SEQUENCE','START','END','OVENBAKE']): continue
        for part in re.split(r'\s*(?:&|,|/)\s*',label):
            part=part.strip()
            if part and part not in {'T','DAY','CONT','D','VO'}:
                names[part.title()]=('role' if part in {'NARRATOR','SINGER','BABY FISH','EGG'} else ('candidate: verify speaker, not scene heading' if len(part.split())>2 or "'" in part or '’' in part else 'script spelling'))
    output=Path(output); existing={}
    if output.exists():
        for l in output.read_text().splitlines():
            cols=[c.strip() for c in l.strip('|').split('|')]
            if l.startswith('| ') and len(cols)>=3 and cols[0] not in {'Name','---'}:existing[cols[0]]=cols[1:3]
    for n in names: existing.setdefault(n,[names[n],''])
    digest=hashlib.sha256(Path(path).read_bytes()).hexdigest()
    result=f'# Character lookup\n\nSource: {Path(path).name}; SHA256: {digest}\n\nNames are spelling hints only; never insert unheard dialogue. Role labels are not proper names.\n\n| Name | Evidence / type | Observed ASR variants |\n| --- | --- | --- |\n'
    result+=''.join(f'| {n} | {v[0]} | {v[1]} |\n' for n,v in sorted(existing.items()))
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(result,encoding='utf-8');return output

def hints(path):
    lines=[]
    for l in Path(path).read_text().splitlines():
        cols=[c.strip() for c in l.strip('|').split('|')]
        if l.startswith('| ') and len(cols)>=3 and cols[0] not in {'Name','---'} and cols[1]=='script spelling':lines.append(cols[0])
    text=Path(path).read_text()
    heading='## User-confirmed speech behavior'
    behavior=text.split(heading,1)[1] if heading in text else ''
    return 'Possible character names (spelling only, do not force into speech): '+', '.join(lines)+('\nUser-confirmed behavior reference (not proof of audible words):\n'+behavior if behavior else '')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('script',type=Path);p.add_argument('output',type=Path);a=p.parse_args();print(extract(a.script,a.output))
