"""Emulate only the recovered RAM initialization; stop before hardware/main."""
from pathlib import Path
import sys, json, struct, hashlib
sys.path.insert(0,str(Path(__file__).resolve().parent/'.tools'))
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_HOOK_CODE,UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_SP
b=Path('firmware_dump/flash_cpu_pass1.bin').read_bytes()
u=Uc(UC_ARCH_ARM,UC_MODE_THUMB);u.mem_map(0,0x20000);u.mem_write(0,b)
u.mem_map(0x20000000,0x10000);u.mem_write(0x20000000,b'\xa5'*0x10000)
u.reg_write(UC_ARM_REG_SP,0x20001c50)
writes=[]; reached=[]
def code(uc,address,size,data):
 if address==0xcd80: reached.append(address);uc.emu_stop()
def write(uc,access,address,size,value,data):
 if not 0x20000000<=address<0x20010000: raise RuntimeError(f'Unexpected non-RAM write {address:x}')
 writes.append((address,size))
u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_WRITE,write)
u.emu_start(0x2285,0,count=200000)
assert reached==[0xcd80], 'Did not reach main entry'
a,z=struct.unpack_from('<II',b,0x22a0)
entries=[dict(zip(('source','destination','length','function'),struct.unpack_from('<IIII',b,p))) for p in range(a,z,16)]
regions=[]
for e in entries:
 raw=bytes(u.mem_read(e['destination'],e['length']))
 path=Path(f"firmware_dump/startup_ram_{e['destination']:08x}.bin");path.write_bytes(raw)
 regions.append(dict(**e,file=str(path),sha256=hashlib.sha256(raw).hexdigest(),all_zero=not any(raw)))
r=dict(method='Offline Unicorn execution of original scatter initialization at 0x2284, stopped at main 0xcd80 before peripheral initialization',source_sha256=hashlib.sha256(b).hexdigest(),regions=regions,ram_write_count=len(writes),caveat='Initialized ranges establish addresses used by this image, not total physical SRAM or free memory.')
Path('firmware_dump/startup_ram_analysis.json').write_text(json.dumps(r,indent=2),encoding='utf-8')
print(json.dumps(r,indent=2))
