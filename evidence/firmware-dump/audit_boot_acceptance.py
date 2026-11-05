"""Execute original boot acceptance code against explicitly synthetic metadata.

No hardware access or writes. The actual 0x10000600 information region has not
been captured, so fixture checksums must not be described as its real contents.
"""
from pathlib import Path
import struct,json,sys,hashlib
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'.tools'))
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_HOOK_CODE,UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_SP,UC_ARM_REG_R0,UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7
original=(ROOT/'firmware_dump/flash_cpu_pass1.bin').read_bytes()
boot=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
boot.mem_map(0,0x20000);boot.mem_map(0x20000000,0x4000);boot.mem_write(0,original)
boot.reg_write(UC_ARM_REG_SP,struct.unpack_from('<I',original,0)[0])
startup_reached=[];startup_writes=[]
def boot_code(uc,address,size,user):
 if address==0x700:startup_reached.append(address);uc.emu_stop()
def boot_write(uc,access,address,size,value,user):
 assert 0x20000000<=address and address+size<=0x20000bf0,hex(address)
 startup_writes.append((address,size))
boot.hook_add(UC_HOOK_CODE,boot_code);boot.hook_add(UC_HOOK_MEM_WRITE,boot_write)
boot.emu_start(struct.unpack_from('<I',original,4)[0],0,count=20000)
assert startup_reached==[0x700]
def xor_words(data):
 assert len(data)%4==0
 value=0
 for word, in struct.iter_unpack('<I',data):value^=word
 return value
def overlay_elf(path):
 raw=path.read_bytes();h=struct.unpack_from('<16sHHIIIIIHHHHHH',raw)
 image=bytearray(original)
 for i in range(h[10]):
  kind,offset,vaddr,paddr,filesz,memsz,flags,align=struct.unpack_from('<8I',raw,h[5]+i*h[9])
  if kind==1 and filesz:
   assert 0x2000<=paddr and paddr+filesz<=0x1a000
   image[paddr:paddr+filesz]=raw[offset:offset+filesz]
 return bytes(image),hashlib.sha256(raw).hexdigest()
length=0x1cc00 # Explicit fixture length, captured original USB image extent.
original_xor=xor_words(original[0x2000:0x2000+length])
fixtures=[]
def add(name,image,app_checksum=None,tag=1,size=length,valid_metadata=True,elf_sha=None):
 meta=bytearray(b'\xff'*512)
 struct.pack_into('<III',meta,0x1c,tag,0xffffffff,size)
 struct.pack_into('<I',meta,0x28,original_xor if app_checksum is None else app_checksum)
 checksum=xor_words(meta[:0x1fc])
 struct.pack_into('<I',meta,0x1fc,checksum if valid_metadata else checksum^1)
 u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
 for address,size_map in [(0,0x20000),(0x20000000,0x4000),(0x40000000,0x20000),(0x10000000,0x1000)]:u.mem_map(address,size_map)
 u.mem_write(0,image);u.mem_write(0x10000600,bytes(meta))
 u.reg_write(UC_ARM_REG_SP,0x20000bf0)
 u.reg_write(UC_ARM_REG_R4,0xffffffff) # No configured pin pair in this fixture.
 u.reg_write(UC_ARM_REG_R5,0);u.reg_write(UC_ARM_REG_R6,0x10000600)
 reached=[];trace=[]
 def code(uc,address,instruction_size,user):
  if 0x77c<=address<=0x83c:trace.append(address)
  if address==0x83c:reached.append(address);uc.emu_stop()
 u.hook_add(UC_HOOK_CODE,code)
 u.emu_start(0x77d,0,count=1000000);assert reached
 result=u.reg_read(UC_ARM_REG_R5)
 fixture=dict(name=name,selection=hex(result),selects_boot_server=(result&0xffff)==2,
              application_xor_calculated=hex(xor_words(image[0x2000:0x2000+length])),
              application_xor_expected=hex(struct.unpack_from('<I',meta,0x28)[0]),
              tag=tag,length=size,metadata_checksum_valid=valid_metadata,
              trace=[hex(x) for x in trace],elf_sha256=elf_sha)
 fixtures.append(fixture);return result
assert add('original application, matching synthetic metadata',original)==0
for mode in ['firmware','firmware_via']:
 path=ROOT/f'qmk_port/build/{mode}/nova_qmk_research.elf'
 image,sha=overlay_elf(path)
 assert add(mode+' with stale original checksum',image,elf_sha=sha)==0xffff0002
 assert add(mode+' with updated synthetic app and metadata checksums',image,
            app_checksum=xor_words(image[0x2000:0x2000+length]),elf_sha=sha)==0
assert add('bad metadata XOR',original,valid_metadata=False)==0xffff0002
assert add('tag zero',original,tag=0)==0xffff0002
assert add('zero application length',original,size=0)==0xffff0002
# This also demonstrates no reset-vector range/Thumb check in this segment:
# keep XOR invariant by flipping the same mask in two app words.
bad_vector=bytearray(original)
old=struct.unpack_from('<I',bad_vector,0x2004)[0];mask=old^0
for address in [0x2004,0x2100]:struct.pack_into('<I',bad_vector,address,struct.unpack_from('<I',bad_vector,address)[0]^mask)
assert add('invalid reset vector with compensated XOR',bytes(bad_vector))==0
actual_path=ROOT/'firmware_dump/boot_safety_audit/metadata_10000600.bin'
actual_cases=[]
def check_actual(name,image,metadata,elf_sha=None):
 u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
 for address,size_map in [(0,0x20000),(0x20000000,0x4000),(0x40000000,0x20000),(0x10000000,0x1000)]:u.mem_map(address,size_map)
 u.mem_write(0,image);u.mem_write(0x10000600,metadata)
 u.reg_write(UC_ARM_REG_SP,0x20000bf0);u.reg_write(UC_ARM_REG_R4,struct.unpack_from('<I',metadata,0x100)[0])
 u.reg_write(UC_ARM_REG_R5,0);u.reg_write(UC_ARM_REG_R6,0x10000600)
 reached=[];trace=[];mmio=[]
 def code(uc,address,size,user):
  trace.append(address)
  if address in (0x848,0x8c0):reached.append(address);uc.emu_stop()
 def write(uc,access,address,size,value,user):
  if 0x40000000<=address<0x40020000:mmio.append(dict(address=hex(address),value=hex(value),size=size))
 u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_WRITE,write)
 u.emu_start(0x77d,0,count=1000000);assert reached
 case=dict(name=name,metadata_sha256=hashlib.sha256(metadata).hexdigest(),elf_sha256=elf_sha,
           selects_boot_server=reached==[0x848],selection=hex(u.reg_read(UC_ARM_REG_R5)),
           application_jump_instruction=reached==[0x8c0],
           target=hex(u.reg_read(UC_ARM_REG_R0)) if reached==[0x8c0] else None,
           checksum_function_called=0x40c in trace,mmio_writes=mmio,
           trace=[hex(a) for a in trace if 0x77c<=a<=0x8c0])
 actual_cases.append(case);return case
if actual_path.exists():
 actual=actual_path.read_bytes();assert len(actual)==512
 assert xor_words(actual[:0x1fc])==struct.unpack_from('<I',actual,0x1fc)[0]
 actual_len=struct.unpack_from('<I',actual,0x24)[0]
 assert xor_words(original[0x2000:0x2000+actual_len])==struct.unpack_from('<I',actual,0x28)[0]
 for name,image,sha in [('original',original,None),*[(mode,*overlay_elf(ROOT/f'qmk_port/build/{mode}/nova_qmk_research.elf')) for mode in ['firmware','firmware_via']]]:
  case=check_actual(name+' with captured patch-list metadata',image,actual,sha)
  assert case['application_jump_instruction'] and not case['checksum_function_called']
 corrupt_app=bytearray(original);corrupt_app[0x3000]^=1
 assert check_actual('corrupt application checksum with captured patch-list metadata',bytes(corrupt_app),actual)['application_jump_instruction']
 corrupt_meta=bytearray(actual);corrupt_meta[0x1fc]^=1
 assert check_actual('corrupt metadata checksum, patch list intact',original,bytes(corrupt_meta))['application_jump_instruction']
 bad_patch=bytearray(actual);struct.pack_into('<I',bad_patch,0x150,0x40013000)
 assert check_actual('patch address outside native allowed window',original,bytes(bad_patch))['selects_boot_server']
report=dict(method='Original boot code0x77c..0x83c and original XOR routine0x40c executed in Unicorn',
 source_sha256=hashlib.sha256(original).hexdigest(),
 actual_information_region_captured=actual_path.exists(),information_region=['0x10000600','0x10000800'],
 fixture_length=hex(length),original_fixture_application_xor=hex(original_xor),
 caveat='Normal-mode checksum cases use synthetic metadata. Captured patch-list cases use the live-read metadata, with synthetic MMIO backing and no real device boot/acceptance test.',
 startup=dict(reset=hex(struct.unpack_from('<I',original,4)[0]),main='0x700',
              reached_main=True,ram_writes=len(startup_writes),
              ram_write_min=hex(min(a for a,s in startup_writes)),
              ram_write_max_exclusive=hex(max(a+s for a,s in startup_writes))),
 cases_passed=len(fixtures),cases=fixtures,captured_metadata_cases_passed=len(actual_cases),
 captured_metadata_cases=actual_cases)
(ROOT/'firmware_dump/boot_acceptance_validation.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:v for k,v in report.items() if k not in ('cases','captured_metadata_cases')},indent=2))
