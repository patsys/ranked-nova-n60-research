"""Offline V3 adds one native USB-bootstrap reentry on failure after erase.
No hardware access. Preserves V1/V2 binaries and their evidence.
"""
from pathlib import Path
import runpy,struct,json,hashlib,contextlib,io
ROOT=Path(__file__).resolve().parents[1];OUT=Path(__file__).resolve().parent
with contextlib.redirect_stdout(io.StringIO()):g=runpy.run_path(str(OUT/'build_bounded_stub.py'))
stub=g['stub'];asm=g['asm'];BASE=g['BASE']
asm(0xde,'''
    cmp r0,#16
    blo #0x200000da
    cmp r0,#132
    bhi #0x200000da
    ldr r2,[pc,#0x3c]
    cmp r4,r2
    bne #0x200000da
    ldrh r2,[r4,#4]
    subs r2,#255
    subs r2,#255
    subs r2,#2
    bne #0x200000da
    cmp r3,#0
    beq #0x20000100
    b #0x2000010e
''',30)
asm(0x100,'''
    push {r3,r4,r5,r6,r7,lr}
    mov r4,r0
    movs r2,#0x84
    lsls r2,#4
    adds r2,#9
    str r2,[sp,#84]
    b #0x20000028
''',14)
asm(0x10e,'''
    ldr r2,[pc,#0x18]
    cmp r1,r2
    bne #0x200000da
    push {r1,r2,r3,r4,r5,r6,r7,lr}
    mov r7,r0
    b #0x20000130
''',12)
asm(0x11a,'''
    ldr r1,[pc,#0x10]
    movs r2,#0
    str r2,[r1]
    push {r4,r5,r6,lr}
    b #0x2000013c
''',10)
struct.pack_into('<III',stub,0x124,g['CTX'],g['SRC'],0x20000214)
asm(0x130,'''
    cmp r0,#132
    bne #0x20000070
    movs r2,#0
    str r2,[sp,#40]
    b #0x20000070
''',10)
asm(0x13a,'b #0x2000011a',2)
binary=OUT/'bounded_stock_stub_v3.bin';binary.write_bytes(stub)
(OUT/'bounded_stock_stub_v3.disasm.txt').write_text('\n'.join(f'{i.address:08x} {i.bytes.hex():12s} {i.mnemonic:8s} {i.op_str}' for i in g['cs'].disasm(bytes(stub),BASE)))
cases=[]
for old in g['cases']:cases.append(g['case'](int(old['entry'],16),page=old['page'],length=old['length'],context=int(old['context'],16),source=int(old['source'],16)))
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_HOOK_MEM_WRITE
from unicorn.arm_const import *
patch_cases=[]
for page in (0,16,132,133):
 for offset in (0x24,0x6c):
  u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
  for a,n in [(0,0x20000),(BASE,0x10000),(0x40013000,0x1000)]:u.mem_map(a,n)
  u.mem_write(0,g['flash']);u.mem_write(BASE,g['ram']);u.mem_write(BASE,bytes(stub))
  u.mem_write(0x20000754,struct.pack('<III',0x5a5a5a5a,0xa5a5a5a5,0x5555aaaa))
  u.mem_write(g['CTX']+4,struct.pack('<H',512));u.mem_write(g['SRC'],b'\xa5'*512)
  sp=0x2000f000;u.mem_write(sp+8,struct.pack('<I',1));u.mem_write(sp+60,struct.pack('<I',0x87f))
  for reg,v in [(UC_ARM_REG_SP,sp),(UC_ARM_REG_LR,0x1ff01),(UC_ARM_REG_R0,page),(UC_ARM_REG_R1,g['SRC']),(UC_ARM_REG_R4,g['CTX'])]:u.reg_write(reg,v)
  events=[]
  def write(u,x,a,s,v,_):
   if sp<=a<BASE+0x10000 or a==0x40013000:events.append({'address':hex(a),'size':s,'value':v,'pc':hex(u.reg_read(UC_ARM_REG_PC))})
  u.hook_add(UC_HOOK_MEM_WRITE,write);u.emu_start(BASE+offset+1,0x1ff00,count=100000)
  ram_writes=[e for e in events if int(e['address'],16)<BASE+0x10000]
  valid=16<=page<=132
  expected=[]
  if valid and offset==0x24:expected=[{'address':hex(sp+60),'size':4,'value':0x849,'pc':'0x2000010a'}]
  if valid and offset==0x6c and page==132:expected=[{'address':hex(sp+8),'size':4,'value':0,'pc':'0x20000136'}]
  assert ram_writes==expected,(page,offset,ram_writes)
  if expected and offset==0x24:assert events[0]==expected[0] and events[1]['address']=='0x40013000'
  patch_cases.append({'page':page,'entry':hex(offset),'extra_ram_writes':ram_writes,'before_controller_command':offset==0x24 and valid,'passed':True})
xor=0
for v in struct.unpack('<110I',stub):xor^=v
result={'passed':True,'byte_length':440,'sha256':hashlib.sha256(stub).hexdigest(),'xor32':hex(xor),'valid_page_operations':234,'cases':cases,'patch_cases':patch_cases,'failure_reentry':'Everyvalid erase first replacesnativeouter savedLR[outerSP+60] with849, soerror/timeoutreturns to originalUSBbootstrap848 ratherthanoriginal87e cleanup/reset. Lastvalidpage132 clearsactive[outerSP+8] forin-sessionreadback.','limitation':'One native bootstrap reentry only. A subsequent fresh nativeBDC session starts with87F again unless a separate hold/reentry mechanism renews it. Powerloss recovery andphysicalcontroller behavior are not established.','model':'Original vendor bodies/nativeABI,guardfixtureandRAM-likeMMIO. Nativefullprotocolandfailuretestsareseparate.'}
(OUT/'bounded_stock_stub_v3_validation.json').write_text(json.dumps(result,indent=2))
print(json.dumps({k:v for k,v in result.items() if k not in ('cases','patch_cases')},indent=2))
