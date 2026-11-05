"""Build and validate an application-only vendor-derived440-byte RAM stub.

Offline only. No HID, device access, installation, or flash operations on real
hardware are performed. Native controller registers are modeled as RAM.
"""
from pathlib import Path
import sys,struct,json,hashlib
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.tools'))
from keystone import Ks,KS_ARCH_ARM,KS_MODE_THUMB
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_HOOK_MEM_WRITE,UC_HOOK_CODE
from unicorn.arm_const import *
OUT=Path(__file__).resolve().parent
BASE=0x20000000;CTX=0x20000324;SRC=CTX+8
MIN_PAGE=16;MAX_PAGE=132
original=(ROOT/'vendor_stub.bin').read_bytes()
assert len(original)==440
stub=bytearray(original);ks=Ks(KS_ARCH_ARM,KS_MODE_THUMB)
def asm(offset,source,size):
    data=bytes(ks.asm(source,BASE+offset)[0]);assert len(data)==size,(hex(offset),len(data),size,source)
    stub[offset:offset+size]=data
asm(0x24,'movs r3,#0; b #0x200000de',4)
asm(0x6c,'movs r3,#1; b #0x200000de',4)
asm(0xda,'movs r0,#2; bx lr',4)
asm(0xfc,'movs r0,#2; bx lr',4)
asm(0xde,'''
    cmp r0,#16
    blo #0x20000112
    cmp r0,#132
    bhi #0x20000112
    ldr r2,[pc,#0x38]
    cmp r4,r2
    bne #0x20000112
    ldrh r2,[r4,#4]
    subs r2,#255
    subs r2,#255
    subs r2,#2
    bne #0x20000112
    cmp r3,#0
    beq #0x20000100
    b #0x20000106
''',30)
asm(0x100,'push {r3,r4,r5,r6,r7,lr}; mov r4,r0; b #0x20000028',6)
asm(0x106,'''
    ldr r2,[pc,#0x1c]
    cmp r1,r2
    bne #0x20000112
    push {r1,r2,r3,r4,r5,r6,r7,lr}
    mov r7,r0
    b #0x20000070
''',12)
asm(0x112,'movs r0,#2; bx lr',4)
asm(0x116,'''
    ldr r1,[pc,#0x10]
    movs r2,#0
    str r2,[r1]
    push {r4,r5,r6,lr}
    b #0x2000013c
''',10)
struct.pack_into('<III',stub,0x120,CTX,SRC,0x20000214)
# Fill unused freed special-function area with trap instructions.
stub[0x12c:0x13a]=b'\x00\xde'*7
asm(0x13a,'b #0x20000116',2)
allowed=set(range(0x24,0x28))|set(range(0x6c,0x70))|set(range(0xda,0x13c))
assert all(a==b or i in allowed for i,(a,b) in enumerate(zip(original,stub)))
binary=OUT/'bounded_stock_stub.bin';binary.write_bytes(stub)
cs=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS)
(OUT/'bounded_stock_stub.disasm.txt').write_text('\n'.join(f'{i.address:08x} {i.bytes.hex():12s} {i.mnemonic:8s} {i.op_str}' for i in cs.disasm(bytes(stub),BASE)))
flash=(ROOT/'firmware_dump/flash_cpu_pass1.bin').read_bytes()
ram=(ROOT/'firmware_dump/boot_initial_ram.bin').read_bytes()
def case(offset,page=16,length=512,context=CTX,source=SRC):
    u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
    for a,n in [(0,0x20000),(BASE,0x10000),(0x40013000,0x1000)]:u.mem_map(a,n)
    u.mem_write(0,flash);u.mem_write(BASE,ram);u.mem_write(BASE,bytes(stub))
    u.mem_write(0x20000754,struct.pack('<III',0x5a5a5a5a,0xa5a5a5a5,0x5555aaaa))
    u.mem_write(CTX+4,struct.pack('<H',length))
    data=struct.pack('<128I',*((0xa55a0000^page^i) for i in range(128)))
    u.mem_write(SRC,data)
    for reg,value in [(UC_ARM_REG_SP,0x2000f000),(UC_ARM_REG_LR,0x1ff01),
                      (UC_ARM_REG_R0,page),(UC_ARM_REG_R1,source),(UC_ARM_REG_R4,context)]:u.reg_write(reg,value)
    writes=[]
    def write(u,x,a,s,v,_):
        if 0x40013000<=a<0x40014000:writes.append((a,v))
    u.hook_add(UC_HOOK_MEM_WRITE,write)
    u.emu_start((BASE+offset)|1,0x1ff00,count=100000)
    assert u.reg_read(UC_ARM_REG_PC)==0x1ff00
    status=u.reg_read(UC_ARM_REG_R0)
    valid=offset in (0x24,0x6c) and MIN_PAGE<=page<=MAX_PAGE and length==512 and context==CTX and (offset==0x24 or source==SRC)
    addresses=[v for a,v in writes if a==0x40013004];commands=[v for a,v in writes if a==0x40013000]
    if valid:
        assert status==0,(offset,page,status)
        assert addresses==([page<<7] if offset==0x24 else [(page<<7)+i for i in range(128)])
        assert commands==([2] if offset==0x24 else [1]*128)
        if offset==0x6c:assert [v for a,v in writes if a==0x40013008]==list(struct.unpack('<128I',data))
    else:assert status==2 and not writes,(offset,page,status,writes)
    return {'entry':hex(offset),'page':page,'length':length,'context':hex(context),'source':hex(source),'accepted':valid,'status':status,'command_count':len(commands),'first_word_address':hex(addresses[0]) if addresses else None,'last_word_address':hex(addresses[-1]) if addresses else None,'passed':True}
cases=[]
for page in range(MIN_PAGE,MAX_PAGE+1):
    for offset in (0x24,0x6c):cases.append(case(offset,page))
for page in (0,15,133,207,208,255,256,0xffffffff):
    for offset in (0x24,0x6c):cases.append(case(offset,page))
for length in (0,1,4,508,511,513,516,65535):
    for offset in (0x24,0x6c):cases.append(case(offset,length=length))
for context in (0,CTX-4,CTX+4,0xffffffff):
    for offset in (0x24,0x6c):cases.append(case(offset,context=context))
for source in (0,SRC-4,SRC+4,SRC+1,0x20000554,0xffffffff):cases.append(case(0x6c,source=source))
for offset in (0xda,0xfc):cases.append(case(offset))
# Timing wrapper clears crypto and enters original timing routine with R0 intact.
u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
for a,n in [(0,0x20000),(BASE,0x10000),(0x40013000,0x1000)]:u.mem_map(a,n)
u.mem_write(0,flash);u.mem_write(BASE,ram);u.mem_write(BASE,bytes(stub));u.mem_write(0x20000214,b'\x01\0\0\0')
u.reg_write(UC_ARM_REG_R0,48000000);u.reg_write(UC_ARM_REG_SP,0x2000f000);u.reg_write(UC_ARM_REG_LR,0x1ff01)
timing=[]
def code(u,a,s,_):
    if a==BASE+0x13c:
        assert u.reg_read(UC_ARM_REG_R0)==48000000
        assert u.reg_read(UC_ARM_REG_SP)==0x2000eff0
        assert bytes(u.mem_read(0x20000214,4))==b'\0'*4
        timing.append('original_timing_entered_with_clock_and_stack_preserved')
u.hook_add(UC_HOOK_CODE,code);u.emu_start(BASE+0x13b,0x1ff00,count=100000)
assert u.reg_read(UC_ARM_REG_PC)==0x1ff00 and u.reg_read(UC_ARM_REG_R0)==0 and timing
xor=0
for offset in range(0,440,4):xor^=struct.unpack_from('<I',stub,offset)[0]
result={'passed':True,'file':str(binary),'byte_length':440,'sha256':hashlib.sha256(stub).hexdigest(),'original_sha256':hashlib.sha256(original).hexdigest(),'xor32':hex(xor),'min_page':MIN_PAGE,'max_page':MAX_PAGE,'cpu_start':'0x2000','cpu_end_exclusive':'0x10a00','native_context':hex(CTX),'native_source':hex(SRC),'required_payload_length':512,'special_metadata_entries_disabled':['0xda','0xfc'],'crypto_flag_cleared':'0x20000214','timing':timing,'valid_page_operations':234,'cases':cases,'method':'Original vendor operation bodies/timing and recovered startupRAM/native ABI helpers executed; controllerMMIO modeled as RAM withbusyclear. No mocked function returns, no hardware access.','limitation':'Offline command containment and data-store verification do not establish physical controller permissions, actual erase/program success or recovery behavior.'}
(OUT/'bounded_stock_stub_validation.json').write_text(json.dumps(result,indent=2))
print(json.dumps({k:v for k,v in result.items() if k!='cases'},indent=2))
