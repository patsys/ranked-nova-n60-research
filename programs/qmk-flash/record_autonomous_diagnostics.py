"""Persist USB audit, diagnostic builds and observed third-trial outcomes."""
from pathlib import Path
import json,hashlib,sqlite3
ROOT=Path(__file__).resolve().parents[1]
TRIAL='qmk_flash/live_qmk_20261103T073628_065587Z/result.json'
paths=[
 'qmk_flash/DIAGNOSTIC_PLAN.md','qmk_flash/manifest.json',
 'qmk_flash/flash_firmware.py','qmk_flash/prepare_image.py',
 'qmk_flash/native_body_protocol_validation.json','qmk_flash/host_tests/validation.json',
 'qmk_flash/read_diagnostic_trace.py','qmk_flash/read_diagnostic_trace_validation.json',
 'qmk_flash/ram_usb/feasibility.json',
 'qmk_port/usb/EVENT4_RESET_FIX.md','qmk_port/usb/device_validation.json',
 'qmk_port/usb/irq_audit/outer_irq_validation.json',
 'qmk_port/usb/diagnostic_validation/validation.json',
 'qmk_port/runtime/usb_diagnostic.c','qmk_port/runtime/usb_diagnostic.h',
 'qmk_port/runtime/main.c','qmk_port/runtime/timebase.c',
 'qmk_port/runtime/usb_keyboard.c','qmk_port/usb/ranked_usb_device.c',
 'qmk_port/runtime/usb_diagnostic_validation.json',
 'qmk_port/runtime/emergency_boot_diagnostic_validation.json',
 'qmk_port/via/via_protocol_diagnostic_result.json',
 'qmk_port/via/transport_diagnostic_validation.json',
 'qmk_port/scan/qmk_pipeline_diagnostic_result.json',
]
facts=[('USB event and IRQ corrections', 'Native instruction comparisons identified and corrected missing event4 endpoint setup and missing fresh status reads before each IRQ acknowledgement. Event4 negative control detects old omission; seven top-level IRQ cases cover status0..3 and conditional asynchronous arrivals. These are proved differences, not proof of physical failure cause. Evidence qmk_port/usb/device_validation.json and usb/irq_audit/outer_irq_validation.json.'),
 ('Bounded diagnostic QMK preparation','Separate diagnostic image records256 bytes at20003000..30ff, uses fault stack3100..31af, requests original boot on unconfigured5000-tick deadline or captured fault. Twenty actual-ELF guard/fault/priority/retention cases and41 emergency cases pass. Fault stack minimum20003158 within proven area. Basic ELFeaf0774f0378e0a042e0f4c204e9ca74154ba248a1a8f614b81e326a75598ba4, VIA ELFce5c886ff99477f440d504088bc717d372a284c9fc8761c27e922057d11c61f1, bodye5ab469df3bb873cb5ac218fb9b698a4f302a288595a193772632456d30b39ad. No claim of independent hardware recovery. Full RAM-only USB takeover was not executed because loader/window and unbounded reinitialization constraints are unresolved.')]
if (ROOT/TRIAL).exists():
 result=json.loads((ROOT/TRIAL).read_text())
 if 'outcome' in result:
  paths.append(TRIAL)
  summary={k:result.get(k) for k in ['verified','released','passed','outcome','target_sha256','bootloader_unchanged','outside_application_unchanged','hidden_metadata_unchanged','final_state']}
  facts.append(('Diagnostic QMK physical trial',json.dumps(summary,sort_keys=True)+'. Evidence '+TRIAL))
# Include finalized matching rollback sessions and any trace files, never infer
# their outcome from presence alone.
for folder in (ROOT/'qmk_flash').glob('live_rollback_*'):
 p=folder/'result.json'
 if not p.exists():continue
 r=json.loads(p.read_text())
 if r.get('elf_sha256')!='ce5c886ff99477f440d504088bc717d372a284c9fc8761c27e922057d11c61f1' or 'outcome' not in r:continue
 paths.append(p.relative_to(ROOT).as_posix())
 trace=folder/'diagnostic_trace.json'
 if trace.exists():paths.append(trace.relative_to(ROOT).as_posix())
 facts.append(('Diagnostic trace and stock recovery',json.dumps({k:r.get(k) for k in ['passed','verified','outcome','bootloader_unchanged','hidden_metadata_unchanged','diagnostic_trace','diagnostic_trace_error','final_state']},sort_keys=True)+'. Evidence '+p.relative_to(ROOT).as_posix()))
with sqlite3.connect(ROOT/'ranked_re.db') as db:
 for name in paths:
  raw=(ROOT/name).read_bytes();db.execute('INSERT OR IGNORE INTO porting_evidence_artifacts(path,sha256,content) VALUES (?,?,?)',(name,hashlib.sha256(raw).hexdigest(),raw.decode('utf-8-sig')))
 for topic,finding in facts:
  if not db.execute('SELECT 1 FROM findings WHERE topic=? AND finding=?',(topic,finding)).fetchone():
   print('Finding',db.execute('INSERT INTO findings(topic,finding) VALUES (?,?)',(topic,finding)).lastrowid)
 for mode in ['firmware_diagnostic','firmware_via_diagnostic']:
  folder=ROOT/'qmk_port/build'/mode;elf=(folder/'nova_qmk_research.elf').read_bytes();manifest=(folder/'firmware_manifest.json').read_text()
  digest=hashlib.sha256(elf).hexdigest();assert json.loads(manifest)['elf_sha256']==digest
  db.execute('INSERT OR IGNORE INTO firmware_builds(sha256,file_path,kind,manifest_json,elf) VALUES (?,?,?,?,?)',(digest,(folder/'nova_qmk_research.elf').relative_to(ROOT).as_posix(),'Bounded USB diagnostic QMK; see physical trial outcome separately',manifest,elf))
 assert db.execute('PRAGMA quick_check').fetchone()[0]=='ok'
print('Saved',len(paths),'text artifacts and diagnostic build bytes')
