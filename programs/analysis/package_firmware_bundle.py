"""Package recovered artifacts and a consistent current SQLite backup."""
from pathlib import Path
import sqlite3,json,hashlib,zipfile

root=Path(__file__).resolve().parent
staging=root/'firmware_bundle'; staging.mkdir(exist_ok=True)
source=sqlite3.connect(root/'ranked_re.db')
finding='Prepared complete recovered-evidence bundle. Coverage is verified CPU-visible0x00000000..0x0001ffff (128KiB), not proof that all physical RAM/OTP/fuses/key material has been obtained. Bundle includes both matching flash passes, bootloader/application regions, disassembly, USB evidence, scripts, captures, and consistent current SQLite backup. Current unknowns are firmware_dump/COVERAGE.md. Archive is analysis evidence, not an installable image.'
source.execute('INSERT INTO findings(topic,finding) VALUES (?,?)',('recovered-artifact-bundle-and-coverage',finding))
fid=source.execute('select last_insert_rowid()').fetchone()[0]
source.commit()
backup_path=staging/'ranked_re.db'
backup=sqlite3.connect(backup_path)
source.backup(backup)
assert backup.execute('pragma quick_check').fetchone()[0]=='ok'
backup.close()
findings=[dict(zip(['id','topic','finding'],r)) for r in source.execute('select id,topic,finding from findings order by id')]
(staging/'findings_current.json').write_text(json.dumps(findings,indent=2),encoding='utf-8')
source.close()

files=[]
for folder in ['firmware_dump','readonly_stub']:
    files.extend(p for p in (root/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
files.extend(root.glob('*.py'))
files.extend(root.glob('*.json'))
files.extend(root.glob('*.md'))
files.extend(root.glob('*.pcap'))
files.extend(root.glob('*.html'))
files.extend(root.glob('*.bin'))
files.extend(root.glob('findings_export.txt'))
files=sorted(set(files))
entries=[dict(path=str(p.relative_to(root)).replace('\\','/'),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files]
for p in [backup_path,staging/'findings_current.json']:
    entries.append(dict(path=p.name,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
inventory=dict(latest_finding=fid,scope='All recovered artifacts; no dependencies/cache or unrecovered chip memory',files=entries)
(staging/'inventory.json').write_text(json.dumps(inventory,indent=2),encoding='utf-8')
archive=root/'ranked_nova_recovered_firmware_bundle.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in files: z.write(p,p.relative_to(root))
    for p in [backup_path,staging/'findings_current.json',staging/'inventory.json']: z.write(p,p.name)
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
print(json.dumps(dict(archive=str(archive),bytes=archive.stat().st_size,files=len(entries)+1,
                      sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),latest_finding=fid),indent=2))
