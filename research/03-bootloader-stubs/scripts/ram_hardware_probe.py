"""Bounded16-byte RAM challenge/CPUID probe; no DATA or COMPLETE commands."""
from pathlib import Path
import struct,json,hashlib,secrets,functools
from usb_block_reader import build_block,mov32,BASE,ENTRIES
from timing_channel import Channel,probe
from keystone import Ks,KS_ARCH_ARM,KS_MODE_THUMB
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_HOOK_MEM_WRITE,UC_HOOK_CODE,UC_HOOK_MEM_READ
from unicorn.arm_const import *
ART=Path('ram_hardware_test');ART.mkdir(exist_ok=True)
MAGIC=0x214d4152;XOR=0xa55a3cc3

def build(nonce):
 image=bytearray(build_block(0x101c,6)[0]);image[0x140:]=b'\x70\x47'*60
 asm='mov r2,r4; adds r2,#8; '+mov32('r0',MAGIC)+'; str r0,[r2]; '+mov32('r0',nonce)+'; str r0,[r2,#4]; '+mov32('r3',XOR)+'''; eors r0,r3; str r0,[r2,#8]; '''+mov32('r0',0xe000ed00)+'''; ldr r0,[r0]; str r0,[r2,#12];
 movs r1,#16; strh r1,[r4,#4]; mov r0,r4; adds r0,#255; adds r0,#255; adds r0,#2; ldr r0,[r0,#20]; blx r0;
 movs r3,#14; lsls r3,#8; adds r3,#0x71; bx r3
 '''
 code=bytes(Ks(KS_ARCH_ARM,KS_MODE_THUMB).asm(asm,BASE+0x140)[0]);assert len(code)<=120
 image[0x140:0x140+len(code)]=code
 # Native control flow; mock only USB callback and read-only CPUID value.
 u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);u.mem_map(0,0x20000);u.mem_map(BASE,0x4000);u.mem_map(0xe000e000,0x1000)
 u.mem_write(0,Path('firmware_dump/flash_cpu_pass1.bin').read_bytes());u.mem_write(0xa00,b'\x70\x47');u.mem_write(BASE,bytes(image));u.mem_write(0xe000ed00,struct.pack('<I',0x410cc200))
 sp=BASE+0x1000;ctx=BASE+0x2000;u.reg_write(UC_ARM_REG_SP,sp);u.mem_write(sp+36,struct.pack('<5I',ctx,5,6,7,0xcc3));u.mem_write(ctx+0x214,struct.pack('<I',0xa01));writes=[];replies=[];reads=[]
 u.hook_add(UC_HOOK_MEM_WRITE,lambda uc,a,p,n,v,d:writes.append((p,n)))
 u.hook_add(UC_HOOK_MEM_READ,lambda uc,a,p,n,v,d:reads.append((p,n)),begin=0xe000e000,end=0xe000efff)
 u.hook_add(UC_HOOK_CODE,lambda uc,a,n,d:replies.append(bytes(uc.mem_read(ctx+8,16))),begin=0xa00,end=0xa00)
 u.emu_start(0x101d,0xe70,count=1000)
 assert replies==[struct.pack('<4I',MAGIC,nonce,nonce^XOR,0x410cc200)]
 assert reads==[(0xe000ed00,4)]
 assert all((p in [sp-8,sp-4,sp+52] and n==4) or (p==ctx+4 and n==2) or (ctx+8<=p<=ctx+20 and n==4) for p,n in writes),writes
 for off in ENTRIES:
  if off!=0x13a:assert image[off:off+4]==b'\x00\x20\x70\x47'
 return bytes(image),dict(nonce=nonce,sha256=hashlib.sha256(image).hexdigest(),offline_native_path_passed=True,stub_bytes=440,reply_bytes=16)

def run_live():
 channel=Channel();log=dict(kind='SmallRAMchallengeandCPUID only; not fullQMK/VIA RAMexecution',trials=[],persistent_caveat='Vendor mode transitions previously appended bookkeeping records; no own flash operations')
 try:
  channel.open();log['version']=channel.version
  assert channel.version['version_words_hex']==['a1050000','a1040000']
  for trial in range(3):
   nonce=secrets.randbits(32);image,spec=build(nonce);frame=bytearray(channel.original);frame[52:492]=image
   struct.pack_into('<I',frame,492,functools.reduce(int.__xor__,struct.unpack('<110I',image),0))
   for pos in range(0,len(frame),64):assert channel.h.write(b'\0'+bytes(frame[pos:pos+64]).ljust(64,b'\0'))==65
   reply=bytes(channel.h.read(65,2000))
   if len(reply)==65 and reply[0]==0:reply=reply[1:]
   spec['reply_hex']=reply.hex();log['trials'].append(spec)
   assert len(reply)==64 and reply[:4]==bytes.fromhex('01000073') and reply[6:8]==bytes.fromhex('0177')
   assert struct.unpack_from('<H',reply,4)[0]==16
   magic,echo,computed,cpuid=struct.unpack_from('<4I',reply,8)
   assert (magic,echo,computed)==(MAGIC,nonce,nonce^XOR)
   spec['cpuid']=f'0x{cpuid:08x}';spec['challenge_verified']=True
   (ART/f'probe_{trial}.bin').write_bytes(image)
  assert len({t['cpuid'] for t in log['trials']})==1
  log['passed']=True
 except Exception as error:
  log['error']=repr(error);log['passed']=False
 finally:
  if channel.h:
   try:log['normal_START']=channel.send(probe('cal',0)[0])
   except Exception as error:log['normal_START_error']=repr(error)
  log['cleanup']=channel.close();(ART/'result.json').write_text(json.dumps(log,indent=2),encoding='utf-8')
 print(json.dumps(log,indent=2));return log

if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--live',action='store_true');args=p.parse_args()
 if args.live:run_live()
 else:
  image,spec=build(0x12345678);(ART/'offline_probe.bin').write_bytes(image);(ART/'offline_validation.json').write_text(json.dumps(spec,indent=2));print(spec)
