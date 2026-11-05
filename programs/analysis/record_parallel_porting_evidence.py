"""Save parallel offline porting evidence in SQLite without modifying old findings."""
from pathlib import Path
import sqlite3,hashlib,json
ROOT=Path(__file__).resolve().parent
names=['startup_ram_analysis.json','usb_driver_analysis.md','usb_tx_offline_traces.json','key_scan_analysis.md','key_scan_tables.json','qmk_platform_analysis.md']
c=sqlite3.connect(ROOT/'ranked_re.db')
c.execute('CREATE TABLE IF NOT EXISTS porting_evidence_artifacts (path TEXT NOT NULL, sha256 TEXT NOT NULL, recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, content TEXT NOT NULL, PRIMARY KEY(path,sha256))')
saved=[];missing=[]
paths=[ROOT/'firmware_dump'/name for name in names]
paths += [ROOT/'firmware_dump'/name for name in ['clock_offline_traces.json','vector_forwarding_validation.json','usb_control_analysis.md']]
paths += [p for p in (ROOT/'qmk_port').rglob('*') if p.is_file() and p.suffix in {'.c','.h','.md','.mk','.json','.py','.S','.ld'}]
paths += [ROOT/'.build-tools'/name for name in ['toolchain_manifest.json','README.md','setup.ps1','env.ps1','env.sh']]
for p in paths:
 name=p.relative_to(ROOT).as_posix()
 if not p.exists():missing.append(name);continue
 raw=p.read_bytes();relative=p.relative_to(ROOT).as_posix();digest=hashlib.sha256(raw).hexdigest()
 cur=c.execute('INSERT OR IGNORE INTO porting_evidence_artifacts(path,sha256,content) VALUES (?,?,?)',(relative,digest,raw.decode('utf-8-sig')))
 if cur.rowcount:saved.append(relative)
c.commit();assert c.execute('PRAGMA quick_check').fetchone()[0]=='ok'
print(json.dumps(dict(saved=saved,missing=missing),indent=2))

