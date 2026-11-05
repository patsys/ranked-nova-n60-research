"""Offline fixed-host identity/preimage/failure tests. All live entry APIs mocked.
Fake execution logs are isolated under host_tests, never under live task paths.
"""
from pathlib import Path
import sys,json,struct,types,contextlib,io
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import qmk_flash.flash_firmware as host
config=host.artifacts('qmk');info=(ROOT/'firmware_dump/boot_safety_audit/metadata_10000600.bin').read_bytes()
cases=[]
def checked(name,function):
 function();cases.append(dict(case=name,passed=True))
def rejected(function):
 try:function()
 except RuntimeError:return
 raise AssertionError('Expected rejection')
original=config['original'];qmkfull=original[:host.START]+config['qmk']+original[host.END:]
for mode,image in [('qmk',original),('rollback',original),('rollback',qmkfull)]:
 expected,old=host.verify_preimage(image,info,mode,config if mode=='qmk' else {**config,'body':config['stock']})
 assert expected[:host.START]+expected[host.END:]==image[:host.START]+image[host.END:]
 cases.append(dict(case='known preimage accepted '+mode+' '+old[:8],passed=True))
checked('QMK refuses QMK preimage',lambda:rejected(lambda:host.verify_preimage(qmkfull,info,'qmk',config)))
bad=bytearray(original);bad[host.START+123]^=1
checked('rollback refuses partial/unknown application',lambda:rejected(lambda:host.verify_preimage(bytes(bad),info,'rollback',config)))
badboot=bytearray(original);badboot[12]^=1
checked('changed bootloader rejected',lambda:rejected(lambda:host.verify_preimage(bytes(badboot),info,'qmk',config)))
checked('changed hidden information rejected',lambda:rejected(lambda:host.verify_preimage(original,bytes([info[0]^1])+info[1:],'qmk',config)))
settings=bytearray(original);settings[0x1a200]^=1
expected,_=host.verify_preimage(bytes(settings),info,'qmk',config);assert expected[0x1a200]==settings[0x1a200]
cases.append(dict(case='vendor settings preimage preserved exactly',passed=True))
keyboard=dict(usage_page=1,usage=6,serial_number=None)
raw=dict(usage_page=0xff60,usage=0x61,serial_number=None)
stockapps=[dict(usage_page=0,usage=0,serial_number=None) for _ in range(5)]+[dict(usage_page=0xff00,usage=0,serial_number='rankednova')]
assert host.identity_state([keyboard,raw],[])['qmk_expected_identity']
assert not host.identity_state([keyboard,raw],[{}])['qmk_expected_identity']
assert not host.identity_state([keyboard],[])['qmk_expected_identity']
assert not host.identity_state(stockapps,[])['qmk_expected_identity']
assert host.identity_state(stockapps,[])['original_expected_identity']
assert not host.identity_state([], [{}])['qmk_expected_identity']
cases.append(dict(case='stock/QMK/bootloader identities remain distinct',passed=True))

class Handle:
 def __init__(self,words):self.words=words;self.closed=False
 def write(self,data):return len(data)
 def read(self,*args):return bytes.fromhex('0100007314000177')+struct.pack('<5I',*self.words)+bytes(36)
 def close(self):self.closed=True
for label,words,prior,valid in [
 ('mask request valid',[0,1,0x410cc200,0,4],False,True),
 ('existing mask valid',[1,1,0x410cc200,0,4],True,True),
 ('lost previous mask',[0,1,0x410cc200,0,4],True,False),
 ('mask not set',[0,0,0x410cc200,0,4],False,False),
 ('NVIC enabled',[0,1,0x410cc200,1,4],False,False),
 ('SysTick enabled',[0,1,0x410cc200,0,7],False,False),
 ('unknown core',[0,1,0x410cc201,0,4],False,False)]:
 from extract_vendor_stub import extract
 frame,_=extract(ROOT/'fw_update.pcap');channel=types.SimpleNamespace(original=frame,h=Handle(words))
 if valid:host.mask_probe(channel,True,prior)
 else:rejected(lambda:host.mask_probe(channel,True,prior))
 cases.append(dict(case=label,passed=True))

# Mock full host operation. No real HID enumerator, reader, send or receive is
# reachable in these contexts. Synthetic proof lives only in isolated fixtureROOT.
base=ROOT/'qmk_flash/host_tests';base.mkdir(exist_ok=True)
class HoldEntered(BaseException):pass
for scenario in ['DATA_write_error','readback_mismatch','metadata_mismatch','release_error',
                 'prewrite_mismatch','qmk_success','qmk_bootloader_after_release','rollback_success']:
 mode='rollback' if scenario=='rollback_success' else 'qmk'
 cfg={**config,'body':config['stock'],'target_sha':host.STOCK_SHA} if mode=='rollback' else config
 before=qmkfull if mode=='rollback' else original
 expect=before[:host.START]+cfg['body']+before[host.END:]
 fixture=base/scenario;gate=fixture/'qmk_flash/ram_scan';gate.mkdir(parents=True,exist_ok=True)
 (gate/'build').mkdir(exist_ok=True);(gate/'build/ram_scan.bin').write_bytes(b'OFFLINE MOCK SCAN PAYLOAD')
 (gate/'live_result.json').write_text(json.dumps(dict(passed=True,elf_sha256=host.ELF_SHA,body_sha256=host.QMK_SHA,
   released_baseline_passed=True,held_Esc_detected=True,cleanup_original_APP6_BOOT0=True,
   payload_sha256=host.digest(b'OFFLINE MOCK SCAN PAYLOAD'),offline_mock_fixture=True)))
 state=dict(open=(mode=='rollback'),hold=0,reader_close=0,query_close=0,sends=[],metadata_reads=0)
 final=host.identity_state(stockapps,[]) if mode=='rollback' else host.identity_state([keyboard,raw],[])
 if scenario=='qmk_bootloader_after_release':final=host.identity_state([], [dict(path=b'OFFLINE')])
 class FakeChannel:
  def __init__(self):self.h=Handle([1,1,0x410cc200,0,4]);self.original=frame;self.version=dict(version_words_hex=['a1050000','a1040000'])
  def close(self):state['query_close']+=1;self.h.close();self.h=None;return final
 class FakeReader:
  def __init__(self):self.channel=FakeChannel()
  def open(self):state['open']=True
  def close(self):state['reader_close']+=1;self.channel.h.close();self.channel.h=None;return dict(final_state=host.identity_state(stockapps,[]))
 def enum(vid,pid):
  if (vid,pid)==(0x3532,0xa0a3):return [] if state['open'] else stockapps
  if (vid,pid)==(0x352d,0x1101):return [dict(path=b'OFFLINE')] if state['open'] else []
  raise AssertionError('Unexpected enumeration')
 def snap(reader,path,stage):
  value=before if stage=='prewrite_backup' else expect
  if scenario=='prewrite_mismatch' and stage=='prewrite_backup':value=bytes(bad)
  if scenario=='readback_mismatch' and stage=='readback_verify':value=value[:0x2345]+bytes([value[0x2345]^1])+value[0x2346:]
  path.write_bytes(value);return value
 def meta(reader):
  state['metadata_reads']+=1
  return bytes([info[0]^1])+info[1:] if scenario=='metadata_mismatch' and state['metadata_reads']>1 else info
 def send(channel,data):
  state['sends'].append(bytes(data))
  if scenario=='DATA_write_error' and data[0]==2:raise OSError('OFFLINE simulated partial DATA write failure')
  if scenario=='release_error' and bytes(data[52:492])==cfg['release']:raise OSError('OFFLINE simulated release failure')
 def receive(channel,packet,sequence,length):return bytes([packet,sequence,0,0x73,length,0,1,0x77,4])+bytes(55)
 def hold(*args):state['hold']+=1;raise HoldEntered()
 patches=dict(ROOT=fixture,artifacts=lambda m:cfg,BlockReader=FakeReader,hid=types.SimpleNamespace(enumerate=enum),
              acquisition_evidence=lambda:('OFFLINE inherited scan evidence','OFFLINE payload','OFFLINE component proof'),
              read_trace=lambda *args:dict(offline_mock_fixture=True,signature_valid=True),
              snapshot=snap,metadata=meta,send=send,receive=receive,mask_probe=lambda *a,**k:dict(primask_after=1),
              hold_after_error=hold,wait_final=lambda m:final)
 caught=None;returned=None
 with patch.multiple(host,**patches),contextlib.redirect_stdout(io.StringIO()):
  try:returned=host.main(mode,True)
  except BaseException as error:caught=error
 logs=list((fixture/'qmk_flash').glob('live_*/result.json'));require_log=logs[-1]
 log=json.loads(require_log.read_text())
 if scenario in ('DATA_write_error','readback_mismatch','metadata_mismatch','release_error'):
  assert isinstance(caught,HoldEntered) and state['hold']==1 and state['reader_close']==state['query_close']==0
  assert log['write_started'] and not log['released']
  assert log['verified']==(scenario=='release_error')
 elif scenario=='prewrite_mismatch':
  assert isinstance(caught,RuntimeError) and state['reader_close']==1 and not log['write_started'] and not state['hold']
 else:
  assert caught is None and state['query_close']==1 and not state['hold'] and log['verified'] and log['released']
  assert returned==(2 if scenario=='qmk_bootloader_after_release' else 0)
  assert log['passed']==(scenario!='qmk_bootloader_after_release')
 cases.append(dict(case=scenario,passed=True,simulated=True))
previous=(host.PREVIOUS_DIR/'qmk_via_application_pages.bin').read_bytes()
previousfull=original[:host.START]+previous+original[host.END:]
upgradebody=(ROOT/'qmk_port/rgb/first_trial_artifacts/qmk_via_application_pages.bin').read_bytes()
assert host.digest(upgradebody)==host.UPGRADE_SOURCE_SHA
upgradefull=original[:host.START]+upgradebody+original[host.END:]
with patch.object(host,'UPGRADE_FROM_QMK',True):
 expected,_=host.verify_preimage(upgradefull,info,'qmk',config)
 assert expected[host.START:host.END]==config['qmk']
 checked('upgrade refuses stock preimage',lambda:rejected(lambda:host.verify_preimage(original,info,'qmk',config)))
 checked('upgrade refuses different QMK preimage',lambda:rejected(lambda:host.verify_preimage(qmkfull,info,'qmk',config)))
 checked('upgrade refuses stale rollback image',lambda:rejected(lambda:host.verify_preimage(previousfull,info,'qmk',config)))
 cases.append(dict(case='upgrade accepts pinned previous QMK only',passed=True))
 # Entry must fail before creating a transport if the application is present.
 with patch.object(host,'acquisition_evidence',lambda:('mock','mock','mock')),patch.object(host,'hid',types.SimpleNamespace(enumerate=lambda vid,pid:[keyboard,raw] if vid==0x3532 else [])),patch.object(host,'BlockReader',side_effect=AssertionError('Transport must not open')):
  checked('upgrade requires exclusive bootloader before transport',lambda:rejected(lambda:host.main('qmk',True)))
with patch.object(host,'ROLLBACK_PREVIOUS',True):
 rollback=host.artifacts('rollback')
 assert rollback['body']==previous and rollback['target_sha']==host.PREVIOUS_SHA
 expected,_=host.verify_preimage(qmkfull,info,'rollback',rollback)
 assert expected[host.START:host.END]==previous
 cases.append(dict(case='previous QMK rollback target and preimage validated',passed=True))
report=dict(passed=True,hardware_access=False,case_count=len(cases),cases=cases,
 fixture_note='Full-host failures use fake transports and isolated synthetic logs under qmk_flash/host_tests; no real --execute operation was called.')
(base/'validation.json').write_text(json.dumps(report,indent=2))
print(f'PASS: {len(cases)} offline host cases; no real HID calls or device writes.')
