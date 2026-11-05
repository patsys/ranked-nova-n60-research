"""Save one completed diagnostic flash/rollback and its matching build evidence."""
from pathlib import Path
import argparse,json,hashlib,sqlite3
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('result');args=p.parse_args()
path=ROOT/args.result;r=json.loads(path.read_text());assert 'outcome' in r
manifest=json.loads((ROOT/'qmk_flash/manifest.json').read_text())
assert r['elf_sha256']==manifest['elf_sha256'],'Current artifacts belong to another iteration'
paths=[path,ROOT/'qmk_flash/manifest.json',ROOT/'qmk_flash/flash_firmware.py',ROOT/'qmk_flash/prepare_image.py',
       ROOT/'qmk_flash/native_body_protocol_validation.json',ROOT/'qmk_flash/host_tests/validation.json',
       ROOT/'qmk_flash/ram_scan/inherited_observations_proof.json',
       ROOT/'qmk_port/usb/device_validation.json',ROOT/'qmk_port/usb/irq_audit/outer_irq_validation.json',
       ROOT/'qmk_port/build/shared_startup_validation/validation.json',
       ROOT/'qmk_port/runtime/usb_diagnostic_validation.json',ROOT/'qmk_flash/read_diagnostic_trace_validation.json']
paths += [ROOT/x['file'] for x in manifest['test_evidence']]
build_folder=(ROOT/manifest['elf_file']).parent
build=json.loads((build_folder/'firmware_manifest.json').read_text())
for rec in build['compiled_sources']+build['configuration_headers']:
    source=ROOT/rec['source'];raw=source.read_bytes();assert hashlib.sha256(raw).hexdigest()==rec['sha256']
    paths.append(source)
trace=path.parent/'diagnostic_trace.json'
if trace.exists():paths.append(trace)
summary={k:r.get(k) for k in ['mode','elf_sha256','target_sha256','verified','released','passed','outcome',
 'bootloader_unchanged','outside_application_unchanged','hidden_metadata_unchanged','final_state']}
if trace.exists():
    decoded=json.loads(trace.read_text())
    summary['trace_signature_valid']=decoded.get('signature_valid')
    if decoded.get('signature_valid'):summary['trace']=decoded['trace']
finding=json.dumps(summary,sort_keys=True)+'. Evidence: '+path.relative_to(ROOT).as_posix()
with sqlite3.connect(ROOT/'ranked_re.db') as db:
    for artifact in set(paths):
        raw=artifact.read_bytes();db.execute('INSERT OR IGNORE INTO porting_evidence_artifacts(path,sha256,content) VALUES (?,?,?)',
            (artifact.relative_to(ROOT).as_posix(),hashlib.sha256(raw).hexdigest(),raw.decode('utf-8-sig')))
    topic='Autonomous diagnostic iteration'
    if not db.execute('SELECT 1 FROM findings WHERE topic=? AND finding=?',(topic,finding)).fetchone():
        print('Finding',db.execute('INSERT INTO findings(topic,finding) VALUES (?,?)',(topic,finding)).lastrowid)
    elf=(ROOT/manifest['elf_file']).read_bytes();assert hashlib.sha256(elf).hexdigest()==r['elf_sha256']
    db.execute('INSERT OR IGNORE INTO firmware_builds(sha256,file_path,kind,manifest_json,elf) VALUES (?,?,?,?,?)',
        (r['elf_sha256'],manifest['elf_file'],'USB diagnostic iteration; physical result stored separately',json.dumps(build),elf))
    assert db.execute('PRAGMA quick_check').fetchone()[0]=='ok'
print(json.dumps(summary,indent=2))
