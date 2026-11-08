"""Check actual linked QMK ELF placement/startup/boot forwarding offline."""
from pathlib import Path
import struct,json,sys,argparse,hashlib
parser=argparse.ArgumentParser();parser.add_argument('--via',action='store_true');parser.add_argument('--diagnostic',action='store_true');parser.add_argument('--keymap',choices=['default','neo2'],default='default');parser.add_argument('--rgb',action='store_true');args=parser.parse_args()
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'.tools'))
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_HOOK_CODE,UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_SP,UC_ARM_REG_IPSR
OUT=ROOT/(('qmk_port/build/firmware_via' if args.via else 'qmk_port/build/firmware')+('_diagnostic' if args.diagnostic else '')+('_neo2' if args.keymap=='neo2' else ''))
if args.rgb:OUT=OUT.with_name(OUT.name+'_rgb')
elf=(OUT/'nova_qmk_research.elf').read_bytes()
assert elf[:6]==b'\x7fELF\x01\x01'
header=struct.unpack_from('<16sHHIIIIIHHHHHH',elf)
entry,phoff,phsize,phnum=header[4],header[5],header[9],header[10]
symbols={}
for line in (OUT/'nova_qmk_research.nm').read_text().splitlines():
 p=line.split()
 if len(p)==3:symbols[p[2]]=int(p[0],16)
original=(ROOT/'firmware_dump/flash_cpu_pass1.bin').read_bytes()
flash=bytearray(original);loads=[]
for i in range(phnum):
 kind,offset,vaddr,paddr,filesz,memsz,flags,align=struct.unpack_from('<8I',elf,phoff+i*phsize)
 if kind!=1:continue
 if filesz:
    assert 0x2000<=paddr and paddr+filesz<=0x1a000
    flash[paddr:paddr+filesz]=elf[offset:offset+filesz]
 loads.append(dict(vaddr=hex(vaddr),paddr=hex(paddr),filesz=filesz,memsz=memsz))
assert flash[:0x2000]==original[:0x2000] and flash[0x1a000:]==original[0x1a000:]
vectors=struct.unpack_from('<40I',flash,0x2000)
assert entry==vectors[1] and vectors[20]==symbols['Vector50']|1
assert vectors[15]==symbols['SysTick_Handler']|1
u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
u.mem_map(0,0x20000);u.mem_map(0x20000000,0x4000)
u.mem_write(0,bytes(flash));u.mem_write(0x20000000,b'\xa5'*0x4000)
u.reg_write(UC_ARM_REG_SP,0x20001c50);writes=[];reached=[]
def code(uc,address,size,user):
 if address==symbols['main']:reached.append(address);uc.emu_stop()
def write(uc,access,address,size,value,user):
 assert 0x20000000<=address and address+size<=0x20001c50,hex(address)
 writes.append((address,size))
u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_WRITE,write)
u.emu_start(entry,0,count=50000);assert reached
data_base,data_end=symbols['__data_base__'],symbols['__data_end__']
data_load=next(int(x['paddr'],16) for x in loads if int(x['vaddr'],16)==data_base)
assert bytes(u.mem_read(data_base,data_end-data_base))==bytes(flash[data_load:data_load+data_end-data_base])
bss_base,bss_end=symbols['__bss_base__'],symbols['__bss_end__']
assert bytes(u.mem_read(bss_base,bss_end-bss_base))==bytes(bss_end-bss_base)
forwarded=[]
for index in [2,3,11,14,15,*range(16,38)]:
 uc=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);uc.mem_map(0,0x20000);uc.mem_write(0,bytes(flash))
 target=vectors[index]&~1;seen=[]
 def stop_at_handler(machine,address,size,user):
    if address==target:seen.append(address);machine.emu_stop()
 uc.reg_write(UC_ARM_REG_IPSR,index);uc.hook_add(UC_HOOK_CODE,stop_at_handler)
 uc.emu_start(0x1df,0,count=20);assert seen==[target]
 forwarded.append(dict(exception=index,target=hex(target)))
result=dict(passed=True,kind='Actual linked QMK ELF offline startup and vector validation',
 elf_sha256=hashlib.sha256(elf).hexdigest(),
 entry=hex(entry),main=hex(symbols['main']),vector_base=hex(symbols['_vectors']),
 data_bytes=data_end-data_base,bss_bytes=bss_end-bss_base,
 startup_ram_writes=len(writes),startup_reached_main=True,
 preserved_boot_and_vendor_data=True,program_headers=loads,
 forwarding_cases=forwarded,forwarding_case_count=len(forwarded),
 usb_irq4_vector=hex(vectors[20]),systick_vector=hex(vectors[15]),
 hardware_tested=False,installed=False,
 limitation='Stops before main peripheral initialization. Synthetic IPSR checks do not simulate physical exception entry/return or timing.')
(OUT/'elf_validation.json').write_text(json.dumps(result,indent=2))
print(json.dumps({k:v for k,v in result.items() if k not in ['program_headers','forwarding_cases']},indent=2))
