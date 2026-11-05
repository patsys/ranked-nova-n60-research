"""Persist observed QMK failure and stock recovery without changing old records."""
from pathlib import Path
import hashlib, json, sqlite3

ROOT = Path(__file__).resolve().parent
paths = [
    'qmk_flash/live_qmk_20261103T062706_170286Z/result.json',
    'qmk_flash/live_rollback_20261103T064616_159843Z/result.json',
    'qmk_flash/ram_scan/live_result.json',
    'qmk_flash/ram_scan/cold_start_audit.md',
    'qmk_flash/ram_scan/cold_readiness_validation.json',
    'firmware_dump/recovery_recheck_after_qmk.md',
    'firmware_dump/boot_reset_recovery_audit.md',
    'firmware_dump/boot_safety_audit/factory_clock_read_result.json',
    'firmware_dump/boot_safety_audit/factory_clock_read_validation.json',
    'qmk_flash/RECOVERY_RESULT_20261103.md',
]
paths += [p.relative_to(ROOT).as_posix() for folder in ['qmk_port/runtime','qmk_port/platform','qmk_port/scan','qmk_port/usb'] for p in (ROOT/folder).glob('*') if p.is_file() and p.suffix in {'.c','.h','.md','.py'}]
paths += [
    'qmk_port/scan/cold_fix_tests/result.json',
    'qmk_port/usb/delay_validation/validation.json',
    'qmk_port/build/clock_calibration_validation/validation.json',
    'qmk_port/runtime/emergency_boot_validation.json',
    'qmk_port/scan/qmk_pipeline_result.json',
    'qmk_port/via/via_protocol_result.json',
    'qmk_port/via/transport_validation.json',
]
facts = [
    ('QMK first physical flash result', 'Application flash/readback verified, bootloader/outside-application/hidden metadata unchanged, but QMK USB runtime did not enumerate. Warm RAM acquisition tests did not validate cold startup. Evidence: qmk_flash/live_qmk_20261103T062706_170286Z/result.json.'),
    ('QMK recovery and stock rollback', 'After user reconnected holding Esc alone, read-only Windows PnP and HID enumeration observed original 352D:1101 vendor interface. Guarded stock rollback then passed full 128KiB expected-image comparison and hidden metadata comparison, with original six HID collections and rankednova identity restored. Evidence: qmk_flash/live_rollback_20261103T064616_159843Z/result.json. This proves recovery on this attempt, not universal cold-start recovery reliability.'),
    ('QMK startup defects identified', 'Offline comparison found USB init callback using short DDE8 delay instead of native long DD80 for steps 1,1,6; omitted EA20(4,0) clock trim and original long startup delays 100/300; emergency hook exits on first empty scan. These are confirmed implementation differences, not a proven single physical failure cause.'),
    ('Factory clock configuration read', 'Bounded read-only native-path stub read exactly four bytes at 0x10000234: 0x06a20060. Native formula gives nominal 48MHz (not physical frequency measurement), trim field 0x600 and 0x40019010 value 0x600a2. No DATA or COMPLETE; original six app HID collections returned. Evidence: firmware_dump/boot_safety_audit/factory_clock_read_result.json.'),
    ('Corrected QMK offline builds', 'After verified stock recovery, corrected clock calibration, long USB delays, 100/300 original-unit startup settling, bounded same-key readiness retries and detected-init-failure bootloader routing. Basic ELF 102808c482f631857f157668f98efc73afa2c5901c5b973c0f4bc08dd6ccdc66; VIA ELF b9a2a24a88ab55638a1ebf2226c7cd815517f2136f835a1d64e53bba8817d1fb. Rebuilt startup, emergency, key pipeline, VIA and transport checks pass offline. Neither corrected build installed or hardware validated; device remains restored stock. Original flash payload/host SHA pins not changed.'),
]
with sqlite3.connect(ROOT/'ranked_re.db') as db:
    db.execute('CREATE TABLE IF NOT EXISTS porting_evidence_artifacts (path TEXT NOT NULL, sha256 TEXT NOT NULL, recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, content TEXT NOT NULL, PRIMARY KEY(path,sha256))')
    saved=[]
    for name in paths:
        raw=(ROOT/name).read_bytes()
        db.execute('INSERT OR IGNORE INTO porting_evidence_artifacts(path,sha256,content) VALUES (?,?,?)', (name,hashlib.sha256(raw).hexdigest(),raw.decode('utf-8-sig')))
    for topic,finding in facts:
        if not db.execute('SELECT 1 FROM findings WHERE topic=? AND finding=?',(topic,finding)).fetchone():
            saved.append(db.execute('INSERT INTO findings(topic,finding) VALUES (?,?)',(topic,finding)).lastrowid)
    for mode in ['firmware','firmware_via']:
        folder=ROOT/'qmk_port/build'/mode
        manifest=(folder/'firmware_manifest.json').read_text()
        elf=(folder/'nova_qmk_research.elf').read_bytes()
        digest=hashlib.sha256(elf).hexdigest()
        assert json.loads(manifest)['elf_sha256']==digest
        emergency=json.loads((ROOT/'qmk_port/runtime/emergency_boot_validation.json').read_text())
        assert emergency['passed'] and emergency['elf_sha256'][mode]==digest
        db.execute('INSERT OR IGNORE INTO firmware_builds(sha256,file_path,kind,manifest_json,elf) VALUES (?,?,?,?,?)',
                   (digest,(folder/'nova_qmk_research.elf').relative_to(ROOT).as_posix(),'Corrected cold startup QMK offline build; NOT installed/hardware validated',manifest,elf))
    assert db.execute('PRAGMA quick_check').fetchone()[0]=='ok'
print(json.dumps({'finding_ids_added':saved,'artifact_count':len(paths)}))
