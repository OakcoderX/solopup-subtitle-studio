"""Validate iTT using a schema obtained separately from its authorized owner."""
import argparse,json
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('itt',type=Path);p.add_argument('--schema',type=Path,required=True,help='Authorized local RelaxNG schema; not bundled');a=p.parse_args()
if not a.schema.is_file():raise SystemExit('Schema not found; no official schema verification was performed.')
try:from lxml import etree
except ImportError:raise SystemExit('Install lxml for optional schema validation; no schema verification was performed.')
v=etree.RelaxNG(etree.parse(str(a.schema)));ok=v.validate(etree.parse(str(a.itt)));print(json.dumps({'schema_valid':ok,'errors':str(v.error_log),'editorial_acceptance':'not established by schema validation'}));raise SystemExit(0 if ok else 1)
