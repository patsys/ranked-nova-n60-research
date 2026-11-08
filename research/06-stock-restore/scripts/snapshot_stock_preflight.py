"""Fresh double-read backup; no DATA/COMPLETE or flash programming operations."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,struct,functools
from usb_block_reader import BlockReader
from read_boot_metadata import build,LOW,HIGH
OUT=Path('stock_flash_preparation')/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');OUT.mkdir(parents=True,exist_ok=False)
r=BlockReader();log=dict(kind='Fresh preflight backup only; no stock flash attempted',directory=OUT.as_posix(),passes=[],metadata=[],persistent_caveat='Vendor mode transitions may append bookkeeping. Snapshot is within one boot session, not a promise of post-cleanup byte identity.')
def save(): (OUT/'manifest.json').write_text(json.dumps(log,indent=2),encoding='utf-8')
def meta():
 out=bytearray()
 for a in range(LOW,HIGH,56):
  n=min(56,HIGH-a);image=build(a,n);frame=bytearray(r.channel.original);frame[52:492]=image
  struct.pack_into('<I',frame,492,functools.reduce(int.__xor__,struct.unpack('<110I',image),0))
  for p in range(0,len(frame),64):assert r.channel.h.write(b'\0'+bytes(frame[p:p+64]).ljust(64,b'\0'))==65
  reply=bytes(r.channel.h.read(65,2000))
  if len(reply)==65 and reply[0]==0:reply=reply[1:]
  assert len(reply)==64 and reply[:4]==bytes.fromhex('01000073') and reply[6:8]==bytes.fromhex('0177') and struct.unpack_from('<H',reply,4)[0]==n
  out.extend(reply[8:8+n])
 return bytes(out)
try:
 r.open();log['version']=r.channel.version;save()
 for passno in [1,2]:
  path=OUT/f'flash_pass{passno}.bin'
  with path.open('wb') as stream:
   for a in range(0,0x20000,4096):
    stream.write(r.read(a,4096));stream.flush()
    if a%0x4000==0 or a+4096==0x20000:print(json.dumps(dict(pass_number=passno,bytes_read=a+4096,total=0x20000)),flush=True)
  log['passes'].append(dict(file=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest()));save()
  m=meta();(OUT/f'metadata_pass{passno}.bin').write_bytes(m);log['metadata'].append(dict(file=f'metadata_pass{passno}.bin',sha256=hashlib.sha256(m).hexdigest()));save()
 one=(OUT/'flash_pass1.bin').read_bytes();two=(OUT/'flash_pass2.bin').read_bytes()
 assert one==two and (OUT/'metadata_pass1.bin').read_bytes()==(OUT/'metadata_pass2.bin').read_bytes()
 original=Path('firmware_dump/flash_cpu_pass1.bin').read_bytes();oldmeta=Path('firmware_dump/boot_safety_audit/metadata_10000600.bin').read_bytes()
 log.update(double_read_identical=True,boot_matches_original=one[:0x2000]==original[:0x2000],application_reserved_region_matches_original=one[0x2000:0x1a000]==original[0x2000:0x1a000],metadata_matches_prior_capture=m==oldmeta,changed_byte_count_vs_original=sum(a!=b for a,b in zip(one,original)),first_changed_offsets=[hex(i) for i,(a,b) in enumerate(zip(one,original)) if a!=b][:64],passed=True)
except Exception as e:log.update(passed=False,error=repr(e));raise
finally:
 try:log['cleanup']=r.close()
 finally:save()
print(json.dumps({k:v for k,v in log.items() if k!='first_changed_offsets'},indent=2),flush=True)
