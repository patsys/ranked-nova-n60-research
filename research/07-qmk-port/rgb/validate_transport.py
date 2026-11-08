"""Actual ARM transport vs original init/transfer/packet, plus DMA ownership."""
from pathlib import Path
import sys, json, struct, subprocess, hashlib
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent;OUT=HERE/'validation_build';OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT/'.tools'))
from unicorn import *
from unicorn.arm_const import *
gcc=ROOT/'.build-tools/bin/arm-none-eabi-gcc.exe';elf=OUT/'rgb_transport.elf'
subprocess.run([str(x) for x in [gcc,'-mcpu=cortex-m0','-mthumb','-Os','-g','-ffreestanding','-fno-builtin','-Wall','-Wextra','-Werror','-nostdlib',
    '-Wl,-Ttext=0x18000,-Tdata=0x20005000,-e,rgb_test_init',HERE/'nova_rgb_transport.c',HERE/'transport_harness.c','-lgcc','-o',elf]],check=True)
nm=subprocess.check_output([str(ROOT/'.build-tools/bin/arm-none-eabi-nm.exe'),'-n',str(elf)],text=True)
s={p[2]:int(p[0],16) for line in nm.splitlines() if len(p:=line.split())==3};b=elf.read_bytes()
original=json.loads((HERE/'original_transport_observations.json').read_text());flash=(ROOT/'firmware_dump/flash_cpu_pass1.bin').read_bytes()
cases=[]
class Model:
    def __init__(self,native=False):
        self.u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);self.events=[];self.native=native
        for a,n in [(0,0x20000),(0x20000000,0x10000),(0x40000000,0x20000),(0xe000e000,0x2000)]:self.u.mem_map(a,n)
        if native:self.u.mem_write(0,flash)
        else:
            off=struct.unpack_from('<I',b,28)[0];sz,num=struct.unpack_from('<HH',b,42)
            for i in range(num):
                typ,file,v,_,n,*_=struct.unpack_from('<8I',b,off+i*sz)
                if typ==1 and n:self.u.mem_write(v,b[file:file+n])
        self.u.hook_add(UC_HOOK_MEM_WRITE,self.write);self.u.hook_add(UC_HOOK_CODE,self.code)
    def write(self,u,access,a,n,v,data):
        assert a>=0x20000 and not 0x40013000<=a<0x40014000
        if a>=0x40000000:
            assert a in {0x4001402c,0xe000e180} or 0x40005000<=a<=0x40005040,(hex(a),v)
            self.events.append(dict(kind='write',address=hex(a),value=hex(v),bytes=n))
    def code(self,u,a,n,data):
        if a==(0xdde8 if self.native else s['rgb_test_delay']):
            self.events.append(dict(kind='short_delay',value=u.reg_read(UC_ARM_REG_R0)))
            u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
    def call(self,name,*args):
        for reg,value in zip([UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2],args):self.u.reg_write(reg,value)
        self.u.reg_write(UC_ARM_REG_SP,0x2000f000);self.u.reg_write(UC_ARM_REG_LR,0x1ff01)
        self.u.emu_start((name if isinstance(name,int) else s[name])|1,0x1ff00,count=200000)
        assert self.u.reg_read(UC_ARM_REG_PC)==0x1ff00
        return self.u.reg_read(UC_ARM_REG_R0)
    def set(self,a,v):self.u.mem_write(a,struct.pack('<I',v))
    def get(self,i):return self.call('rgb_test_get',i)
    def tick(self,v):self.set(s['test_ticks'],v)

m=Model();assert m.call('rgb_test_init')==1;assert m.events==original['spi_init_events'];cases.append('exact native SPI initializer write/delay trace')
colors=bytes((plane*70+ch*6+bank)%251 for bank in range(6) for ch in range(11) for plane in range(3))
m.u.mem_write(s['test_colors'],colors);m.events=[];assert m.call('rgb_test_submit')==1
tx,rx=m.get(0),m.get(1);frame=bytes(m.u.mem_read(tx,269));assert frame.hex()==original['frame']['hex'];cases.append('exact native269-byte RGB frame')
assert tx%16==rx%16==0
n=Model(native=True);n.set(0x40005010,0x11);n.call(0x5a74,tx,rx,269);assert m.events==n.events,(m.events,n.events);cases.append('exact native DMA request/start trace')
m.set(0x4000504c,8);m.tick(9);m.u.mem_write(s['test_colors'],bytes([255])*198);m.events=[]
assert m.call('rgb_test_submit')==0 and bytes(m.u.mem_read(tx,269))==frame and not m.events;cases.append('busy transfer cannot mutate DMA-owned TX')
m.tick(10);m.call('rgb_test_poll');assert m.get(3)==1 and m.get(6)==1 and bytes(m.u.mem_read(tx,269))==frame;cases.append('timeout retains busy DMA buffer ownership')
m.set(0x4000504c,0);m.tick(20);m.call('rgb_test_poll');assert m.get(3)==0;cases.append('idle after timeout permits reuse')
assert m.call('rgb_test_submit')==1;m.u.mem_write(rx,b'\xa5');m.set(0x4000504c,1);m.call('rgb_test_poll');assert m.get(5)==1 and m.get(3)==0;cases.append('A5 reply completes transfer')
for status,reply,label in [(3,0xa5,'controller error'),(1,0,'bad controller reply')]:
    m.set(0x4000504c,0);assert m.call('rgb_test_submit')==1
    old=m.get(6);m.u.mem_write(rx,bytes([reply]));m.set(0x4000504c,status);m.call('rgb_test_poll');assert m.get(6)==old+1;cases.append(label)
m.set(0x4000504c,0);m.tick(0xfffffff8);assert m.call('rgb_test_submit')==1
m.tick(1);m.call('rgb_test_poll');assert m.get(3)==1
m.tick(2);m.call('rgb_test_poll');assert m.get(3)==0;cases.append('unsigned10ms timeout across timer wrap')
bad=Model();bad.set(0x4000504c,8);assert bad.call('rgb_test_init')==0 and bad.get(2)==0;cases.append('busy initializer fails without blocking')
assert m.call('nova_rgb_transport_init',0,0)==0;cases.append('null inputs rejected without access')
report=dict(passed=True,case_count=len(cases),cases=cases,hardware_access=False,flash_or_fmc_writes=False,
    elf_sha256=hashlib.sha256(b).hexdigest(),sources={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [HERE/'nova_rgb_transport.c',HERE/'nova_rgb_transport.h']},
    limitation='OriginalSPI register storage modeled; real LED controller response, color order, timing/current and USB coexistence remain physical tests.')
(HERE/'transport_validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
