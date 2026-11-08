"""Read only the metadata region explicitly read by recovered boot code."""
from pathlib import Path
import struct,json,hashlib,functools
from usb_block_reader import build_block,mov32,BASE
from timing_channel import Channel,probe
from keystone import Ks,KS_ARCH_ARM,KS_MODE_THUMB
from unicorn import *
from unicorn.arm_const import *
ART=Path('firmware_dump/boot_safety_audit');ART.mkdir(exist_ok=True)
LOW=0x10000600;HIGH=0x10000800

def build(address,length):
 assert LOW<=address<HIGH and address%4==0 and length%4==0 and 4<=length<=56 and address+length<=HIGH
 image=bytearray(build_block(0x101c,6)[0]);image[0x140:]=b'\x70\x47'*60
 asm=mov32('r0',address)+f'''; mov r2,r4; adds r2,#8; movs r1,#{length//4};
 loop: ldr r3,[r0]; str r3,[r2]; adds r0,#4; adds r2,#4; subs r1,#1; bne loop;
 movs r1,#{length}; strh r1,[r4,#4]; mov r0,r4; adds r0,#255; adds r0,#255; adds r0,#2; ldr r0,[r0,#20]; blx r0;
 movs r3,#14; lsls r3,#8; adds r3,#0x71; bx r3
 '''
 code=bytes(Ks(KS_ARCH_ARM,KS_MODE_THUMB).asm(asm,BASE+0x140)[0]);assert len(code)<=120;image[0x140:0x140+len(code)]=code
 u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
 for a,n in [(0,0x20000),(BASE,0x4000),(0x10000000,0x1000)]:u.mem_map(a,n)
 u.mem_write(0,Path('firmware_dump/flash_cpu_pass1.bin').read_bytes());u.mem_write(BASE,bytes(image));u.mem_write(0xa00,b'\x70\x47')
 sample=bytes((i*19+7)&255 for i in range(512));u.mem_write(LOW,sample)
 sp=BASE+0x1000;ctx=BASE+0x2000;u.reg_write(UC_ARM_REG_SP,sp);u.mem_write(sp+36,struct.pack('<5I',ctx,5,6,7,0xcc3));u.mem_write(ctx+0x214,struct.pack('<I',0xa01))
 writes=[];reads=[];replies=[]
 u.hook_add(UC_HOOK_MEM_WRITE,lambda uc,a,p,n,v,d:writes.append((p,n)))
 u.hook_add(UC_HOOK_MEM_READ,lambda uc,a,p,n,v,d:reads.append((p,n)),begin=0x10000000,end=0x10000fff)
 u.hook_add(UC_HOOK_CODE,lambda uc,a,n,d:replies.append(bytes(uc.mem_read(ctx+8,length))),begin=0xa00,end=0xa00)
 u.emu_start(0x101d,0xe70,count=1000)
 assert replies==[sample[address-LOW:address-LOW+length]]
 assert reads==[(p,4) for p in range(address,address+length,4)]
 assert all((p in [sp-8,sp-4,sp+52] and n==4) or (p==ctx+4 and n==2) or (ctx+8<=p<ctx+8+length and n==4) for p,n in writes)
 return bytes(image)

def main():
 ch=Channel();log=dict(kind='Nativebootmetadataread, noDATA/COMPLETE/ownflashoperations',blocks=[],persistent_caveat='Mode transitions may append vendor bookkeeping');data=bytearray()
 try:
  images=[(a,min(56,HIGH-a),build(a,min(56,HIGH-a))) for a in range(LOW,HIGH,56)]
  ch.open();log['version']=ch.version;assert ch.version['version_words_hex']==['a1050000','a1040000']
  for a,n,image in images:
   frame=bytearray(ch.original);frame[52:492]=image;struct.pack_into('<I',frame,492,functools.reduce(int.__xor__,struct.unpack('<110I',image),0))
   for p in range(0,len(frame),64):assert ch.h.write(b'\0'+bytes(frame[p:p+64]).ljust(64,b'\0'))==65
   reply=bytes(ch.h.read(65,2000))
   if len(reply)==65 and reply[0]==0:reply=reply[1:]
   assert len(reply)==64 and reply[:4]==bytes.fromhex('01000073') and reply[6:8]==bytes.fromhex('0177') and struct.unpack_from('<H',reply,4)[0]==n
   data.extend(reply[8:8+n]);log['blocks'].append(dict(address=hex(a),length=n,stub_sha256=hashlib.sha256(image).hexdigest(),reply_hex=reply.hex(),offline_bounded_reads_writes_passed=True))
  assert len(data)==512;(ART/'metadata_10000600.bin').write_bytes(data)
  words=struct.unpack('<128I',data);xor=functools.reduce(int.__xor__,words[:127],0)
  log.update(passed=True,sha256=hashlib.sha256(data).hexdigest(),metadata_xor=hex(xor),stored_metadata_xor=hex(words[127]),metadata_xor_matches=xor==words[127],tag=hex(words[7]),application_length=hex(words[9]),application_xor=hex(words[10]))
 except Exception as error:log.update(passed=False,error=repr(error))
 finally:
  if ch.h:
   try:log['normal_START']=ch.send(probe('cal',0)[0])
   except Exception as e:log['normal_START_error']=repr(e)
  log['cleanup']=ch.close();(ART/'metadata_read_result.json').write_text(json.dumps(log,indent=2),encoding='utf-8')
 print(json.dumps({k:v for k,v in log.items() if k!='blocks'},indent=2))
if __name__=='__main__':main()
