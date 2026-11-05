"""Read-only evidence checks for the consolidated process documentation.

Writes only documentation_audit.json. No device API or firmware execution.
Historical build paths may now name newer builds; database ELF BLOBs are
verified by their own hashes instead of assuming old paths stayed immutable.
"""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,re,sqlite3
ROOT=Path(__file__).resolve().parent
DOCS=['REVERSE_ENGINEERING_GUIDE.md','REPORT.md','ANALYSIS_UPDATE.md','COMMUNICATION.md',
      'firmware_dump/COVERAGE.md','firmware_dump/BOOT_CRYPTO_AND_QMK.md',
      'qmk_flash/SUCCESS_20261103.md','qmk_port/README.md',
      'qmk_port/runtime/USB_DIAGNOSTIC.md','qmk_flash/ram_scan/README.md','stock_restore/README.md']
DOCS.append('crypto_research/README.md')
CRITICAL=['fw_update.pcap','layout_cap.pcap','vendor_stub.bin',
          'firmware_dump/flash_cpu_pass1.bin','firmware_dump/flash_cpu_pass2.bin',
          'firmware_dump/boot_safety_audit/metadata_10000600.bin',
          'qmk_flash/manifest.json','qmk_flash/qmk_via_application_pages.bin',
          'qmk_flash/rollback_stock_application_pages.bin',
          'qmk_flash/live_qmk_20261103T062706_170286Z/result.json',
          'qmk_flash/live_qmk_20261103T070202_026538Z/result.json',
          'qmk_flash/live_qmk_20261103T073628_065587Z/result.json',
          'qmk_flash/live_rollback_20261103T073830_059181Z/diagnostic_trace.json',
          'qmk_flash/live_qmk_20261103T075452_444196Z/result.json',
          'qmk_flash/via_live_queries.json','qmk_flash/runtime_soak.json','qmk_flash/via_live_remap.json',
          'qmk_port/runtime/validate_usb_diagnostic.py','qmk_port/build_firmware.py',
          'stock_restore/live_20261103T055849Z/result.json',
          'qmk_flash/live_rollback_20261103T064616_159843Z/result.json',
          'qmk_flash/live_rollback_20261103T070503_261490Z/result.json',
          'qmk_flash/live_rollback_20261103T073830_059181Z/result.json']
CRITICAL += ['crypto_research/extract_update_keys.py','crypto_research/key_extraction_result.json',
             'crypto_research/master_key.bin','crypto_research/captured_file_key.bin',
             'crypto_research/captured_update_plaintext.bin','crypto_research/zero_input_prediction.bin']
def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
report=dict(recorded_at=datetime.now(timezone.utc).isoformat(),hardware_access=False,links=[],artifacts=[])
for name in DOCS:
    path=ROOT/name;text=path.read_text(encoding='utf-8-sig')
    for target in re.findall(r'(?<!!)\[[^\]]+\]\(([^)]+)\)',text):
        if re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:',target) or target.startswith('#'):continue
        target=target.split('#',1)[0].strip('<>')
        resolved=path.parent/target
        assert resolved.exists(),(name,target)
        report['links'].append(dict(source=name,target=target,exists=True))
for name in DOCS+CRITICAL:
    path=ROOT/name;assert path.is_file(),name
    report['artifacts'].append(dict(path=name,bytes=path.stat().st_size,sha256=sha(path)))
manifest=json.loads((ROOT/'qmk_flash/manifest.json').read_text())
assert sha(ROOT/manifest['elf_file'])==manifest['elf_sha256']
assert sha(ROOT/manifest['body_file'])==manifest['body_sha256']
live=json.loads((ROOT/'qmk_flash/live_qmk_20261103T075452_444196Z/result.json').read_text())
assert live['passed'] and live['verified'] and live['target_sha256']==manifest['body_sha256']
assert all(live[k] for k in ['bootloader_unchanged','outside_application_unchanged','hidden_metadata_unchanged'])
for name in ['qmk_flash/runtime_soak.json','qmk_flash/via_live_remap.json']:
    record=json.loads((ROOT/name).read_text());assert record['passed']
    assert record['elf_sha256']==manifest['elf_sha256'] and record['body_sha256']==manifest['body_sha256']
assert json.loads((ROOT/'qmk_flash/via_live_queries.json').read_text())['passed']
crypto=json.loads((ROOT/'crypto_research/key_extraction_result.json').read_text())
assert crypto['passed'] and crypto['independent_saved_physical_source_matches']
assert sha(ROOT/'crypto_research/captured_update_plaintext.bin')==crypto['plaintext_sha256']
assert (ROOT/'crypto_research/master_key.bin').read_bytes().hex()==crypto['master_key_hex']
with sqlite3.connect('file:'+str(ROOT/'ranked_re.db').replace('\\','/')+'?mode=ro',uri=True) as db:
    assert db.execute('PRAGMA quick_check').fetchone()[0]=='ok'
    report['database_snapshot_counts']={n:db.execute('SELECT COUNT(*) FROM "'+n+'"').fetchone()[0] for n, in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    builds=db.execute('SELECT sha256,elf FROM firmware_builds').fetchall()
    for digest,blob in builds:assert hashlib.sha256(blob).hexdigest()==digest
    dumps=db.execute('SELECT name,sha256,content FROM firmware_dumps').fetchall()
    for name,digest,blob in dumps:assert hashlib.sha256(blob).hexdigest()==digest,name
    report.update(database_ELF_blobs_verified=len(builds),database_dump_blobs_verified=len(dumps))
report.update(passed=True,installed_elf_sha256=manifest['elf_sha256'],installed_body_sha256=manifest['body_sha256'])
(ROOT/'documentation_audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(dict(passed=True,links_checked=len(report['links']),artifacts_hashed=len(report['artifacts']),
                     ELF_blobs_verified=report['database_ELF_blobs_verified'],dump_blobs_verified=report['database_dump_blobs_verified'],hardware_access=False)))
