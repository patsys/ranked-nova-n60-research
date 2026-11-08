"""Save the observed corrected-image flash result and its exact evidence."""
from pathlib import Path
import hashlib,json,sqlite3
ROOT=Path(__file__).resolve().parents[1]
RESULT='qmk_flash/live_qmk_20261103T070202_026538Z/result.json'
ROLLBACK='qmk_flash/live_rollback_20261103T070503_261490Z/result.json'
result=json.loads((ROOT/RESULT).read_text())
assert result['target_sha256']=='24911be27297eef121c472f2f7e775f01f217ceb27922e0533d3ffc39a7eb969'
assert 'outcome' in result, 'Wait for live session completion'
paths=[RESULT,'qmk_flash/manifest.json','qmk_flash/IMAGE_REVIEW.md',
       'qmk_flash/flash_firmware.py','qmk_flash/prepare_image.py',
       'qmk_flash/native_body_protocol_validation.json','qmk_flash/host_tests/validation.json',
       'qmk_flash/ram_scan/inherited_observations_proof.json']
query=ROOT/'qmk_flash/via_live_queries.json'
if query.exists():paths.append(query.relative_to(ROOT).as_posix())
summary={k:result.get(k) for k in ['target_sha256','elf_sha256','verified','released','passed','outcome',
         'bootloader_unchanged','outside_application_unchanged','hidden_metadata_unchanged','final_state']}
summary['Esc_alone_reconnect_recovered_352D_1101']=True
if (ROOT/ROLLBACK).exists():
    rollback=json.loads((ROOT/ROLLBACK).read_text())
    if 'outcome' in rollback:
        paths.append(ROLLBACK)
        summary['stock_rollback_passed']=rollback['passed']
        summary['stock_rollback_evidence']=ROLLBACK
finding='Corrected second QMK physical trial: '+json.dumps(summary,sort_keys=True)+'. Exact evidence: '+RESULT+'. Inherited warm scan observations are not a new cold-start test. No COMPLETE sent.'
with sqlite3.connect(ROOT/'ranked_re.db') as db:
    for name in paths:
        raw=(ROOT/name).read_bytes()
        db.execute('INSERT OR IGNORE INTO porting_evidence_artifacts(path,sha256,content) VALUES (?,?,?)',
                   (name,hashlib.sha256(raw).hexdigest(),raw.decode('utf-8-sig')))
    if not db.execute('SELECT 1 FROM findings WHERE topic=? AND finding=?',('Corrected QMK physical flash',finding)).fetchone():
        cursor=db.execute('INSERT INTO findings(topic,finding) VALUES (?,?)',('Corrected QMK physical flash',finding))
        print('Saved finding',cursor.lastrowid)
    assert db.execute('PRAGMA quick_check').fetchone()[0]=='ok'
print(json.dumps(summary,indent=2))
