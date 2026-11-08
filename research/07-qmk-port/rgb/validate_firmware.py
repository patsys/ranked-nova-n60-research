"""Actual linked RGB Matrix/VIA lifecycle with modeled SPI DMA completion."""
from pathlib import Path
import sys,struct,json,hashlib
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'.tools'))
from unicorn import *
from unicorn.arm_const import *
folder=ROOT/'qmk_port/build/firmware_via_diagnostic_neo2_rgb'
elf=(folder/'nova_qmk_research.elf').read_bytes()
s={p[2]:int(p[0],16) for line in (folder/'nova_qmk_research.nm').read_text().splitlines() if len(p:=line.split())==3}
driver_address=next(int(p[0],16) for line in (folder/'nova_qmk_research.nm').read_text().splitlines() if len(p:=line.split())==3 and p[1]=='d' and p[2]=='driver')
u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
for a,n in [(0,0x20000),(0x20000000,0x4000),(0x40000000,0x20000),(0xe000e000,0x2000)]:u.mem_map(a,n)
off=struct.unpack_from('<I',elf,28)[0];size,num=struct.unpack_from('<HH',elf,42)
for i in range(num):
    typ,file,v,_,n,*_=struct.unpack_from('<8I',elf,off+i*size)
    if typ==1 and n:u.mem_write(v,elf[file:file+n])
frames=[];dma=False;now=0;mmio=[];minsp=s['__process_stack_end__']
def read32(a):return int.from_bytes(u.mem_read(a,4),'little')
def code(uc,a,n,data):
    global minsp
    minsp=min(minsp,uc.reg_read(UC_ARM_REG_SP))
    if a in (s['nova_platform_delay_original_units'],s['nova_platform_delay_original_long']):
        uc.reg_write(UC_ARM_REG_R0,1);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
def memory(uc,access,a,n,v,data):
    global dma
    if access==UC_MEM_READ and a==0x4000504c:uc.mem_write(a,struct.pack('<I',1 if dma else 0))
    if access==UC_MEM_WRITE:
        assert a>=0x20000 and not 0x40013000<=a<0x40014000,('flash write',hex(a))
        if a>=0x40000000:mmio.append([hex(a),v])
        if a==0x40005008:dma=False
        if a==0x40005000 and v==1:
            tx,rx,count=read32(0x4000502c),read32(0x40005030),read32(0x40005028)
            assert count==269 and tx%16==rx%16==0
            assert s['__process_stack_end__']<=tx and tx+269<=s['__bss_end__']
            assert s['__process_stack_end__']<=rx and rx+269<=s['__bss_end__']
            frames.append(bytes(uc.mem_read(tx,269)))
            uc.mem_write(rx,b'\xa5');dma=True
u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_READ|UC_HOOK_MEM_WRITE,memory)
def call(name,*args):
    for reg,value in zip([UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3],args):u.reg_write(reg,value&0xffffffff)
    u.reg_write(UC_ARM_REG_SP,s['__process_stack_end__']);u.reg_write(UC_ARM_REG_LR,0x1ff01)
    u.emu_start(s[name]|1,0x1ff00,count=1000000)
    assert u.reg_read(UC_ARM_REG_PC)==0x1ff00,name
def command(data):
    p=0x20001820;u.mem_write(p,bytes(data).ljust(32,b'\0'));u.mem_write(s['raw_tx_pending'],b'\0')
    call('raw_hid_receive',p,32)
    assert u.mem_read(s['raw_tx_pending'],1)==b'\1'
    return bytes(u.mem_read(s['raw_tx'],32))
def render():
    global now
    for _ in range(16):
        now+=20;u.mem_write(s['timer_count'],struct.pack('<I',now));call('rgb_matrix_task')
def check_frame(frame,kind):
    assert frame[:6]==bytes.fromhex('c00b0600fa00')
    matrix=bytes(u.mem_read(s['g_led_config'],66))
    values=[]
    for row in range(6):
        for col in range(11):
            v=tuple(frame[6+p*88+col*8+row] for p in range(3))
            if matrix[row*11+col]==255:assert v==(0,0,0)
            else:values.append(v)
    if kind=='white':assert len(set(values))==1 and values[0][0]>0 and len(set(values[0]))==1
    if kind=='red':assert all(r>0 and g==b==0 for r,g,b in values)
    if kind=='off':assert not any(any(v) for v in values)

cases=[];call('keyboard_init');call('host_set_driver',driver_address)
assert command([8,3,2])[3]==1;assert command([8,3,4])[3:5]==b'\0\0';cases.append('default enabled solid white via standard VIA RGB API')
render();assert frames;check_frame(frames[-1],'white');cases.append('all62 populated positions white; absent positions black; aligned bounded DMA')
assert command([7,3,4,0,255])[:3]==bytes([7,3,4]);render();check_frame(frames[-1],'red');cases.append('standard VIA HSV update renders red')
assert command([7,3,2,0])[:3]==bytes([7,3,2]);render();check_frame(frames[-1],'off');cases.append('standard VIA disable sends black frame')
assert command([8,3,2])[3]==0
for mode in (2,3):
    command([7,3,2,mode]);assert command([8,3,2])[3]==mode;render()
    cases.append('standard VIA effect mode '+str(mode))
command([7,3,2,1]);command([7,3,4,0,0]);render();check_frame(frames[-1],'white');cases.append('reenable white without persistent writes')
before=bytes(u.mem_read(s['colors'],198))
call('rgb_matrix_set_color',-1,255,255,255);call('rgb_matrix_set_color',62,255,255,255)
assert bytes(u.mem_read(s['colors'],198))==before;cases.append('invalid LED indices do not mutate buffer')
old=len(mmio);r=command([2,0x81,0]);assert r[3:5]==b'\1\1' and r[6]==0xa5 and len(mmio)==old
assert int.from_bytes(r[12:16],'big')>0 and int.from_bytes(r[16:20],'big')==0;cases.append('read-only diagnostic reports A5 completions and zero errors')
assert minsp>=s['__process_stack_base__']
report=dict(passed=True,case_count=len(cases),cases=cases,elf_sha256=hashlib.sha256(elf).hexdigest(),
            minimum_process_stack=hex(minsp),frame_count=len(frames),flash_or_fmc_writes=False,hardware_access=False,
            limitation='Modeled SPI completion/A5 reply; physical RGB brightness/color order and USB coexistence still require validation.')
(Path(__file__).parent/'firmware_validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
