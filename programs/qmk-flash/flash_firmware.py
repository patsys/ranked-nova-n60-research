"""Fixed QMK application flash or fixed stock rollback. NO writes by default.

--execute is the only live-operation entry point. This tool sends no COMPLETE.
After an unverified DATA error it runs the reviewed read-only keepalive; losing
power or the host/USB connection can still defeat recovery. No automatic retry.
"""
from pathlib import Path
from datetime import datetime,timezone
import argparse,sys,json,struct,time
if not __debug__:raise SystemExit('Safety assertions required; Python -O is forbidden')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from stock_restore.restore_stock import (BlockReader,hid,digest,send,receive,metadata,snapshot,
 start_frame,hold_after_error,STUB_SHA,RELEASE_SHA,HOLD_SHA,META_SHA,ORIGINAL_SHA,HEADER_SHA)
from qmk_flash.probe_core_state import build as core_stub
QMK_SHA='edd1d456d79546f9da38258e4d9e2a3a8c1a0940791bad8dd2e7868a61272f94'
ELF_SHA='1c63569e9e1dfbf343757fd425856a4891c08a53c4aae54345a465f0cabda88f'
UPGRADE_FROM_QMK=False
UPGRADE_SOURCE_SHA='b16f8b8459bf1bf9a367bf6e84f4de01bd3c3c1457266382268f469e088c5721'
ROLLBACK_PREVIOUS=False
PREVIOUS_SHA='a924b79044fa9c26b92a6ade993b0a74f6f7b1ddbe5d73d3060ff302aa241f80'
PREVIOUS_DIR=ROOT/'qmk_port/rgb/baseline_before_rgb'
STOCK_SHA='7f7f5853e7192c737be85cc00e0b21db56e8a40bd68495900002921ef914762c'
BOOT_SHA='e46c6d9300a13f4d2eea7c16584d24ea6e4e1b83815e5f84f389d4aeb0915f62'
START=0x2000;END=0x10a00
def require(value,message):
 if not value:raise RuntimeError(message)
def read_json(path):return json.loads(path.read_text(encoding='utf-8'))
def artifacts(mode):
 qmk=(ROOT/'qmk_flash/qmk_via_application_pages.bin').read_bytes()
 stock=(ROOT/'qmk_flash/rollback_stock_application_pages.bin').read_bytes()
 previous=(PREVIOUS_DIR/'qmk_via_application_pages.bin').read_bytes()
 require(len(previous)==117*512 and digest(previous)==PREVIOUS_SHA,'Previous working QMK rollback changed')
 require(len(qmk)==len(stock)==117*512,'Fixed application-body length changed')
 require(digest(qmk)==QMK_SHA and digest(stock)==STOCK_SHA,'Fixed target/rollback hash changed')
 require(digest((ROOT/'qmk_port/build/firmware_via_diagnostic_neo2_rgb/nova_qmk_research.elf').read_bytes())==ELF_SHA,'Source Neo2 diagnostic VIA ELF changed')
 manifest=read_json(ROOT/'qmk_flash/manifest.json')
 require(manifest['body_sha256']==QMK_SHA and manifest['elf_sha256']==ELF_SHA and manifest['rollback_sha256']==STOCK_SHA,'Prepared manifest changed')
 require(manifest.get('usb_diagnostic') is True,'Require bounded diagnostic image')
 rgb=read_json(ROOT/'qmk_port/rgb/firmware_validation.json')
 require(manifest.get('rgb_enabled') is True and rgb.get('passed') and rgb['elf_sha256']==ELF_SHA and not rgb['flash_or_fmc_writes'],'RGB firmware proof missing or stale')
 diagnostic=read_json(ROOT/'qmk_port/runtime/usb_diagnostic_neo2_rgb_validation.json')
 require(diagnostic.get('passed') is True and diagnostic['elf_sha256']['firmware_via_diagnostic_neo2_rgb']==ELF_SHA,'Diagnostic timeout/fault proof missing or stale')
 traceproof=read_json(ROOT/'qmk_flash/read_diagnostic_trace_validation.json')
 require(traceproof.get('passed_native_abi') is True and traceproof.get('caller_guards_tested') is True and traceproof.get('no_peripheral_or_flash_writes_by_readers') is True,'Read-only trace transport not validated')
 require(manifest['original_boot_emulation']['passed'] and manifest['source_and_build_validation_bound'],'Prepared image lacks validation')
 original=(ROOT/'firmware_dump/flash_cpu_pass1.bin').read_bytes()
 require(len(original)==0x20000 and digest(original)==ORIGINAL_SHA,'Original reference changed')
 require(original[START:END]==stock and digest(original[:START])==BOOT_SHA,'Rollback/reference mismatch')
 stub=(ROOT/'stock_restore/bounded_stock_stub_v3.bin').read_bytes()
 release=(ROOT/'stock_restore/release_stub.bin').read_bytes()
 holder=(ROOT/'stock_restore/hold_stub.bin').read_bytes()
 require(len(stub)==len(release)==len(holder)==440,'Fixed RAM-stub length changed')
 require(digest(stub)==STUB_SHA and digest(release)==RELEASE_SHA and digest(holder)==HOLD_SHA,'Fixed RAM-stub hash changed')
 bounds=read_json(ROOT/'stock_restore/bounded_stock_stub_v3_validation.json')
 require(bounds['passed'] and bounds['sha256']==STUB_SHA,'Bounded stub unvalidated')
 require({c['page'] for c in bounds['cases'] if c['accepted']}==set(range(16,133)) and bounds['valid_page_operations']==234,'Unexpected programmer bounds')
 for file,expected in [('release_stub_validation.json',RELEASE_SHA),('hold_stub_validation.json',HOLD_SHA)]:
  proof=read_json(ROOT/'stock_restore'/file);require(proof['passed'] and proof['sha256']==expected,'Unvalidated release/hold stub')
 failure=read_json(ROOT/'stock_restore/failure_reentry_v3_validation.json')
 require(failure['passed'] and failure['stub_sha256']==STUB_SHA,'Failure reentry proof missing')
 # Exact QMK payload proof also validates IRQ masking through readback/release.
 proofpath=ROOT/'qmk_flash/native_body_protocol_validation.json'
 protocol=read_json(proofpath)
 require(protocol['passed'] and protocol['body_sha256']==QMK_SHA and protocol['stub_sha256']==STUB_SHA,'QMK protocol proof stale')
 require(protocol['no_COMPLETE'] and protocol['all_program_words_match_body'] and protocol['emulated_readback_matches_body'],'QMK protocol readback/release unvalidated')
 require(protocol['primask_initial']==protocol['primask_final']==1,'Masked transfer proof missing')
 if mode=='rollback' and ROLLBACK_PREVIOUS:
  previous_proof=read_json(PREVIOUS_DIR/'native_body_protocol_validation.json')
  require(previous_proof.get('passed') is True and previous_proof['body_sha256']==PREVIOUS_SHA and previous_proof['no_COMPLETE'] and previous_proof['emulated_readback_matches_body'],'Previous QMK protocol proof missing')
 elif mode=='rollback':
  for file in ['protocol_transition_v3_validation.json','protocol_release_v3_validation.json']:
   p=read_json(ROOT/'stock_restore'/file)
   require(p['passed_native_protocol_audit'] and p['stub_sha256']==STUB_SHA and p['body_sha256']==STOCK_SHA and p['no_COMPLETE'],'Stock protocol proof stale')
 core=read_json(ROOT/'qmk_flash/core_probe/live_result.json')
 require(core['passed'] and core['masked_USB_poll_reply_verified'],'Physical masked polling was not demonstrated')
 masked=next(t for t in core['trials'] if t['mask_requested'])
 require(masked['stub_sha256']==digest(core_stub(True)) and masked['primask_after']==1 and int(masked['nvic_iser'],16)==0 and int(masked['systick_ctrl'],16)&3==0,'Core-mask live proof changed')
 return dict(body=qmk if mode=='qmk' else previous if ROLLBACK_PREVIOUS else stock,target_sha=QMK_SHA if mode=='qmk' else PREVIOUS_SHA if ROLLBACK_PREVIOUS else STOCK_SHA,
             qmk=qmk,stock=stock,original=original,stub=stub,release=release,
             diagnostic=manifest.get('usb_diagnostic',False),
             protocol_sha256=digest(proofpath.read_bytes()))

def read_trace(reader,out):
 from qmk_flash.read_diagnostic_trace import read_diagnostic_trace
 return read_diagnostic_trace(reader,out)

def mask_probe(channel,mask,require_already_masked=False):
 image=core_stub(mask);send(channel,start_frame(channel,image));reply=receive(channel,1,0,20)
 before,after,cpuid,iser,systick=struct.unpack_from('<5I',reply,8)
 require(after==1 and (not require_already_masked or before==1),'Interrupt mask was not preserved')
 require(cpuid==0x410cc200 and iser==0 and systick&3==0,'Unexpected core/IRQ/SysTick state')
 return dict(mask_requested=mask,primask_before=before,primask_after=after,cpuid=hex(cpuid),
             nvic_iser=hex(iser),systick_ctrl=hex(systick),stub_sha256=digest(image),reply_hex=reply.hex())

def verify_preimage(before,info,mode,config):
 require(len(before)==0x20000 and digest(before[:START])==BOOT_SHA,'Bootloader does not match fixed original')
 require(len(info)==512 and digest(info)==META_SHA,'Hidden information block changed')
 bodysha=digest(before[START:END])
 if mode=='qmk':
  if UPGRADE_FROM_QMK:
   require(bodysha==UPGRADE_SOURCE_SHA and before[END:0x1a000]==config['original'][END:0x1a000],'Upgrade requires exact installed RGB trial body and original code tail')
  else:require(before[:0x1a000]==config['original'][:0x1a000] and bodysha==STOCK_SHA,'QMK flash requires exact stock code preimage')
 else:require(bodysha in (QMK_SHA,STOCK_SHA,PREVIOUS_SHA,UPGRADE_SOURCE_SHA),'Rollback refuses unknown/partial application body')
 expected=bytearray(before);expected[START:END]=config['body']
 return bytes(expected),bodysha

def identity_state(apps,boots):
 keyboard=[d for d in apps if d.get('usage_page')==1 and d.get('usage')==6]
 raw=[d for d in apps if d.get('usage_page')==0xff60 and d.get('usage')==0x61]
 vendor=[d for d in apps if d.get('usage_page')==0xff00]
 return dict(application_collections=len(apps),bootloader_interfaces=len(boots),
             qmk_keyboard_collections=len(keyboard),qmk_raw_collections=len(raw),
             qmk_expected_identity=bool(keyboard and raw and len(apps)==2 and not boots),
             original_expected_identity=(len(apps)==6 and not boots and len(vendor)==1 and vendor[0].get('serial_number')=='rankednova'),
             collections=[dict(usage_page=hex(d.get('usage_page',0)),usage=hex(d.get('usage',0)),serial_number=d.get('serial_number')) for d in apps])

def wait_final(mode):
 state={}
 for _ in range(120):
  state=identity_state(hid.enumerate(0x3532,0xa0a3),hid.enumerate(0x352d,0x1101))
  if state['qmk_expected_identity'] if mode=='qmk' or ROLLBACK_PREVIOUS else state['original_expected_identity']:break
  if state['bootloader_interfaces']==1 and state['application_collections']==0:
   # Wait a little longer so a transient reset enumeration does not decide early.
   if _>=30:break
  time.sleep(.1)
 return state

def acquisition_evidence():
 """Prior warm physical observations plus separately proved driver equivalence.

 This is NOT a claim that the corrected cold startup has run on hardware.
 The user authorized its first physical flash after that limitation was stated.
 """
 scanpath=ROOT/'qmk_flash/ram_scan/live_result.json'
 scan=read_json(scanpath)
 require(scan.get('passed') is True and scan.get('elf_sha256')=='11b02d44086d3b658b3479ae64145d58b56f71ebe04a15fceee8c041622782fb' and scan.get('body_sha256')=='071ee8e608a2332b6462a12191260572319706cbc67a96df2d405276848a92ef','Original physical observations changed')
 require(scan.get('released_baseline_passed') is True and scan.get('held_Esc_detected') is True and scan.get('cleanup_original_APP6_BOOT0') is True,'Both released and held-Esc physical scan proof plus stock cleanup required')
 for trial in scan['trials']:
  require(digest((ROOT/trial['path']).read_bytes())==trial['sha256'],'Changed physical trial artifact')
 payload_hash=digest((ROOT/'qmk_flash/ram_scan/build/ram_scan.bin').read_bytes())
 require(scan.get('payload_sha256')==payload_hash,'Physical observations refer to another payload')
 proofpath=ROOT/'qmk_flash/ram_scan/inherited_observations_proof.json'
 require(digest(proofpath.read_bytes())=='abdf178ed9f8494b286978a530bd8644ab651ee2021291c87f1df0b3f8d8e819','Component equivalence proof changed')
 proof=read_json(proofpath)
 require(proof.get('passed_component_equivalence') is True or (
     proof.get('passed_bounded_timing_differential') is True and
     proof.get('original_conversion_delay')==5 and proof.get('trial_conversion_delay')==20 and
     proof.get('previous_body_sha256')==PREVIOUS_SHA and len(proof.get('body_byte_changes',[]))==1 and
     proof.get('case_count')==8 and all(c.get('passed') and c.get('changed_scan_delays')==6 for c in proof.get('cases',[]))
 ) or (
     proof.get('passed_scan_equivalence_to_working_qmk') is True and
     proof.get('working_elf_sha256')=='8fbed3bc051b69ae5005ae2293566ffaeb2c4b91fbf36e7c53c0539bc700c711' and
     proof.get('previous_body_sha256')==PREVIOUS_SHA and proof.get('case_count')==8 and
     all(c.get('passed') for c in proof.get('cases',[])) and
     proof.get('physical_typing_comparison_sha256')==digest((ROOT/'qmk_port/neo2/timing_fix_comparison.json').read_bytes())
 ),'Legacy acquisition or bounded differential missing')
 require(proof.get('new_elf_sha256')==ELF_SHA and proof.get('new_body_sha256')==QMK_SHA,'Component proof refers to another target')
 require(proof.get('originalphysical_gate_sha256')==digest(scanpath.read_bytes()) and proof.get('current_payload_sha256')==payload_hash,'Inherited observations not bound to physical evidence')
 require(proof.get('physical_cold_start_validated') is False,'Do not mislabel inherited observations as a physical cold-start test')
 return digest(scanpath.read_bytes()),payload_hash,digest(proofpath.read_bytes())

def main(mode,execute):
 config=artifacts(mode)
 if not execute:
  print(json.dumps(dict(prepared_only=True,mode=mode,target_sha256=config['target_sha'],pages=117,
        no_COMPLETE=True,requires_live_RAM_scan_gate=(mode=='qmk'),hardware_access=False),indent=2));return 0
 scan_gate_hash=None;scan_payload_hash=None;component_proof_hash=None
 if mode=='qmk':
  scan_gate_hash,scan_payload_hash,component_proof_hash=acquisition_evidence()
 apps=hid.enumerate(0x3532,0xa0a3);boots=hid.enumerate(0x352d,0x1101)
 if mode=='qmk' and UPGRADE_FROM_QMK:
  require(not apps and len(boots)==1,'Upgrade requires exclusive already-present bootloader')
 elif mode=='qmk':
  require(identity_state(apps,boots)['original_expected_identity'],'Require only originalAPP6/rankednova, no bootloader')
 else:require(not apps and len(boots)==1,'Rollback requires exclusive already-present bootloader')
 out=ROOT/'qmk_flash'/datetime.now(timezone.utc).strftime('live_'+mode+'_%Y%m%dT%H%M%S_%fZ');out.mkdir(exist_ok=False)
 log=dict(kind='Fixed QMK application flash' if mode=='qmk' else 'Previous working QMK rollback' if ROLLBACK_PREVIOUS else 'Fixed stock rollback',mode=mode,
          upgrade_from_QMK=UPGRADE_FROM_QMK,rollback_to_previous_QMK=ROLLBACK_PREVIOUS,
          upgrade_source_sha256=UPGRADE_SOURCE_SHA,
          target_sha256=config['target_sha'],stub_sha256=STUB_SHA,elf_sha256=ELF_SHA,
          physical_scan_gate_sha256=scan_gate_hash,physical_scan_payload_sha256=scan_payload_hash,
          inherited_component_proof_sha256=component_proof_hash,corrected_cold_start_physically_validated_before_flash=False,
          no_COMPLETE=True,pages=[],write_started=False,verified=False,released=False,
          protocol_sha256=config['protocol_sha256'],persistent_caveat='Vendor mode transitions may append bookkeeping; same-session outside-target readback must match',
          recovery_caveat='Unverified DATA failure uses read-only keepalive; loss of host/power/USB can defeat recovery. Partial bodies are not accepted by fresh rollback mode.')
 reader=BlockReader();channel=reader.channel
 def save(): (out/'result.json').write_text(json.dumps(log,indent=2),encoding='utf-8')
 def save_best_effort():
  try:save()
  except OSError as error:print('Could not persist result log: '+repr(error),flush=True)
 try:
  reader.open();log['version']=channel.version
  require(not hid.enumerate(0x3532,0xa0a3) and len(hid.enumerate(0x352d,0x1101))==1,'Require exclusive bootloader after entry')
  channel.restore_boot_path=hid.enumerate(0x352d,0x1101)[0]['path']
  if mode=='rollback':require(channel.restore_boot_path==boots[0]['path'],'Rollback bootloader path changed during open')
  log['boot_path_hex']=channel.restore_boot_path.hex() if isinstance(channel.restore_boot_path,bytes) else str(channel.restore_boot_path)
  require(digest(channel.original[:52])==HEADER_SHA,'Captured START header changed')
  log['mask_before_backup']=mask_probe(channel,True);save()
  before=snapshot(reader,out/'before_flash.bin','prewrite_backup')
  mb=metadata(reader);(out/'before_metadata.bin').write_bytes(mb)
  expected,oldbody=verify_preimage(before,mb,mode,config)
  (out/'expected_flash.bin').write_bytes(expected)
  log.update(before_flash_sha256=digest(before),before_metadata_sha256=digest(mb),before_body_sha256=oldbody,
             expected_flash_sha256=digest(expected));save()
  if mode=='rollback' and config.get('diagnostic'):
   try:log['diagnostic_trace']=read_trace(reader,out)
   except Exception as error:log['diagnostic_trace_error']=repr(error)
   save()
   # The existing core probe below must establish a fresh valid response and
   # masked state before any DATA, even if a diagnostic read failed.
  log['mask_before_DATA']=mask_probe(channel,True,True);save()
  send(channel,start_frame(channel,config['stub']));reply=receive(channel,1,0,1)
  require(reply[8]==4,'Bounded START rejected');log['start_reply']=reply.hex();save()
  for index in range(117):
   page=config['body'][index*512:(index+1)*512];sequence=index+1
   frame=bytes([2,sequence,0,0x73,0,2,1,0x77])+page
   log['write_started']=True;save()
   send(channel,frame);reply=receive(channel,2,sequence,1)
   rec=dict(sequence=sequence,page=16+index,cpu_address=hex(START+index*512),sha256=digest(page),native_status=reply[8],reply_hex=reply.hex())
   log['pages'].append(rec);save();require(reply[8]==4,'DATA rejected: '+repr(rec))
   if sequence==1 or sequence%16==0 or sequence==117:print(json.dumps(dict(stage=mode+'_application_write',pages_acknowledged=sequence,total=117)),flush=True)
  log['mask_before_readback']=mask_probe(channel,False,True);save()
  after=snapshot(reader,out/'after_flash.bin','readback_verify')
  ma=metadata(reader);(out/'after_metadata.bin').write_bytes(ma)
  log['mask_after_readback']=mask_probe(channel,False,True)
  log.update(after_flash_sha256=digest(after),after_metadata_sha256=digest(ma),
             target_readback_matches=after[START:END]==config['body'],bootloader_unchanged=after[:START]==before[:START],
             outside_application_unchanged=after[:START]+after[END:]==before[:START]+before[END:],
             hidden_metadata_unchanged=ma==mb,whole_flash_matches_expected=after==expected)
  save();require(after==expected and ma==mb,'Readback mismatch: no release, keep bootloader connected')
  log['verified']=True;save()
  send(channel,start_frame(channel,config['release']));reply=receive(channel,1,0,1)
  require(reply[8]==4,'Verified-image release rejected');log['released']=True;save()
 except BaseException as error:
  log['error']=repr(error);save_best_effort()
  if log['write_started'] and not log['released']:
   hold_after_error(channel,log,save_best_effort)
  # A known QMK preimage must not auto-return to a potentially broken app just
  # because rollback failed before DATA. Stay in the reviewed read-only holder.
  if mode=='rollback' and not log['released'] and channel.h:
   hold_after_error(channel,log,save_best_effort)
  raise
 finally:
  if channel.h:
   if log['released']:
    try:log['cleanup_query']=channel.close()
    except Exception as error:log['cleanup_error']=repr(error)
   elif not log['write_started'] and mode=='qmk':
    try:log['cleanup_before_write']=reader.close()
    except Exception as error:log['cleanup_error']=repr(error)
   else:
    channel.h.close();channel.h=None;log['unverified_session_detached']=True
  save_best_effort()
 state=wait_final(mode);log['final_state']=state
 success=state['qmk_expected_identity'] if mode=='qmk' or ROLLBACK_PREVIOUS else state['original_expected_identity']
 log['passed']=bool(log['verified'] and log['released'] and success)
 if mode=='qmk' and state['bootloader_interfaces']==1 and not state['application_collections']:
  log['outcome']='bootloader_after_verified_QMK_release'
  log['note']='May be emergency any-key entry; QMK runtime is not confirmed. Fresh guarded rollback mode is available for the exact QMK body.'
 elif not success:
  log['outcome']='expected_runtime_not_detected'
  log['action_required']='Physical action may be needed: hold a key and reconnect the keyboard. Early startup/matrix failure can prevent this recovery hook; do not assume recovery.'
 else:log['outcome']='expected_runtime_enumerated'
 save();print(json.dumps(dict(result_file=str((out/'result.json').relative_to(ROOT)),passed=log['passed'],verified=log['verified'],outcome=log['outcome'],final_state=state),indent=2),flush=True)
 return 0 if log['passed'] else 2

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--mode',choices=['qmk','rollback'],default='qmk');parser.add_argument('--execute',action='store_true')
 parser.add_argument('--from-qmk',action='store_true',help='Require pinned previous QMK preimage and already-present bootloader')
 parser.add_argument('--rollback-previous',action='store_true',help='Restore pinned previous working QMK instead of stock')
 args=parser.parse_args()
 if args.from_qmk and args.mode!='qmk':parser.error('--from-qmk requires mode qmk')
 if args.rollback_previous and args.mode!='rollback':parser.error('--rollback-previous requires mode rollback')
 UPGRADE_FROM_QMK=args.from_qmk;ROLLBACK_PREVIOUS=args.rollback_previous
 raise SystemExit(main(args.mode,args.execute))
