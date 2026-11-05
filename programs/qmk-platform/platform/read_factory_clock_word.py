"""Read ONLY the four-byte factory word used by original EA20(4,0).

Default is offline stub validation. --live is an explicit read-only device
session; no DATA/COMPLETE, flash commands, or information-region writes.
"""
from pathlib import Path
import sys,struct,json,hashlib
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'.tools'))
from usb_block_reader import build_block,mov32,BASE,BlockReader
from keystone import Ks,KS_ARCH_ARM,KS_MODE_THUMB
from unicorn import *
from unicorn.arm_const import *
OUT=ROOT/'firmware_dump/boot_safety_audit'
ADDRESS=0x10000234
def build():
 image=bytearray(build_block(0x101c,6)[0]);image[0x140:]=b'\x70\x47'*60
 source=mov32('r0',ADDRESS)+'''; ldr r3,[r0]; str r3,[r4,#8];
 movs r1,#4; strh r1,[r4,#4]; mov r0,r4; adds r0,#255; adds r0,#255; adds r0,#2;
 ldr r0,[r0,#20]; blx r0; movs r3,#14; lsls r3,#8; adds r3,#0x71; bx r3'''
 code=bytes(Ks(KS_ARCH_ARM,KS_MODE_THUMB).asm(source,BASE+0x140)[0]);assert len(code)<=120
 image[0x140:0x140+len(code)]=code
 cases=[]
 for value in (0,0xffffffff,0xdab37f60):
  u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
  for a,n in [(0,0x20000),(BASE,0x4000),(0x10000000,0x1000)]:u.mem_map(a,n)
  u.mem_write(0,(ROOT/'firmware_dump/flash_cpu_pass1.bin').read_bytes());u.mem_write(BASE,bytes(image));u.mem_write(0xa00,b'\x70\x47')
  u.mem_write(ADDRESS,struct.pack('<I',value));sp=BASE+0x1000;ctx=BASE+0x2000
  u.reg_write(UC_ARM_REG_SP,sp);u.mem_write(sp+36,struct.pack('<5I',ctx,5,6,7,0xcc3));u.mem_write(ctx+0x214,struct.pack('<I',0xa01))
  reads=[];writes=[];reply=[]
  u.hook_add(UC_HOOK_MEM_READ,lambda uc,access,a,n,v,d:reads.append((a,n)),begin=0x10000000,end=0x10000fff)
  u.hook_add(UC_HOOK_MEM_WRITE,lambda uc,access,a,n,v,d:writes.append((a,n)))
  u.hook_add(UC_HOOK_CODE,lambda uc,a,n,d:reply.append(bytes(uc.mem_read(ctx+8,4))),begin=0xa00,end=0xa00)
  u.emu_start(0x101d,0xe70,count=1000)
  assert reads==[(ADDRESS,4)] and reply==[struct.pack('<I',value)]
  assert all((a in [sp-8,sp-4,sp+52] and n==4) or (a==ctx+4 and n==2) or (a==ctx+8 and n==4) for a,n in writes)
  cases.append(dict(fixture=hex(value),reads=[dict(address=hex(a),bytes=n) for a,n in reads],passed=True))
 OUT.mkdir(exist_ok=True)
 (OUT/'factory_clock_read_stub.bin').write_bytes(image)
 (OUT/'factory_clock_read_validation.json').write_text(json.dumps(dict(passed=True,sha256=hashlib.sha256(image).hexdigest(),address=hex(ADDRESS),bytes=4,cases=cases,hardware_access=False),indent=2))
 return bytes(image)
def main(live=False):
 image=build()
 if not live:print('PASS: fixed10000234 word-read stub, three native-path fixtures; no hardware access');return
 from stock_restore.restore_stock import hid,send,receive,start_frame,HEADER_SHA,digest
 apps=hid.enumerate(0x3532,0xa0a3)
 assert len(apps)==6 and len([d for d in apps if d.get('usage_page')==0xff00 and d.get('serial_number')=='rankednova'])==1
 assert not hid.enumerate(0x352d,0x1101)
 reader=BlockReader();log=dict(kind='Read only the native-used factory clock word',address=hex(ADDRESS),bytes=4,stub_sha256=digest(image),no_DATA_or_COMPLETE=True,persistent_caveat='Vendor mode transition may append journal bookkeeping')
 try:
  reader.open();log['version']=reader.channel.version
  assert digest(reader.channel.original[:52])==HEADER_SHA
  send(reader.channel,start_frame(reader.channel,image));reply=receive(reader.channel,1,0,4)
  data=reply[8:12];value=struct.unpack('<I',data)[0]
  (OUT/'factory_clock_10000234.bin').write_bytes(data)
  log.update(passed=True,word=hex(value),data_sha256=digest(data),reply_hex=reply.hex(),
    source_hz_formula_24M_plus4M_index=24000000+4000000*((value>>4)&7),
    factory_index_bits4_6=(value>>4)&7,reg1900c_field_8_10=hex((value&0x70)<<4),
    reg19010_value=hex(((value>>16)&0xff)|((value>>8)&0xf0000)))
 except BaseException as error:log.update(passed=False,error=repr(error));raise
 finally:
  log['cleanup']=reader.close();(OUT/'factory_clock_read_result.json').write_text(json.dumps(log,indent=2))
 print(json.dumps(log,indent=2))
if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--live',action='store_true');main(parser.parse_args().live)
