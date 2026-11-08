"""Extract crypto configuration candidate; verify dataflow, not cipher identity.

No HID/device access. Standard-cipher comparisons are hypotheses only.
"""
from pathlib import Path
import sys,struct,json,hashlib,itertools
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'.tools'))
from extract_vendor_stub import extract
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_HOOK_MEM_WRITE
from unicorn.arm_const import *
from cryptography.hazmat.primitives.ciphers import Cipher,algorithms,modes
OUT=ROOT/'crypto_research';OUT.mkdir(exist_ok=True)
flash=(ROOT/'firmware_dump/flash_cpu_pass1.bin').read_bytes()
assert hashlib.sha256(flash).hexdigest()=='5adca278d90a0672e05dfe5ad47d1635242f9ec0ff78827d83d9f28d6ccd8b49'
u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
for a,n in [(0,0x20000),(0x20000000,0x4000),(0x40000000,0x20000),(0xe000e000,0x2000)]:u.mem_map(a,n)
u.mem_write(0,flash);u.reg_write(UC_ARM_REG_SP,0x20000bf0)
u.emu_start(0x1cd,0x700,count=50000);assert u.reg_read(UC_ARM_REG_PC)==0x700
candidate=bytes(u.mem_read(0x2000021c,16))
assert candidate==(ROOT/'firmware_dump/boot_initial_ram.bin').read_bytes()[0x21c:0x22c]
# The pointer is established by native330. Supply only that descriptor field
# to isolate actual398/memcpy behavior without modeling hardware decryption.
u.mem_write(0x20000318,struct.pack('<I',0x200007c0))
u.reg_write(UC_ARM_REG_R0,0x2000021c);u.reg_write(UC_ARM_REG_SP,0x20000b00);u.reg_write(UC_ARM_REG_LR,0x1f001)
writes=[];u.hook_add(UC_HOOK_MEM_WRITE,lambda uc,access,a,n,v,d:writes.append((a,n)))
u.emu_start(0x399,0x1f000,count=1000)
assert u.reg_read(UC_ARM_REG_PC)==0x1f000 and bytes(u.mem_read(0x200007c0,16))==candidate
assert all(0x20000000<=a and a+n<=0x20004000 for a,n in writes)
frame,_=extract(ROOT/'fw_update.pcap')
def transform(data,mode):
    if mode&1:data=b''.join(data[i:i+4][::-1] for i in range(0,16,4))
    if mode&2:data=b''.join([data[i:i+4] for i in range(0,16,4)][::-1])
    if mode&4:data=bytes(data[r+4*c] for r in range(4) for c in range(4))
    return data
matches=[];tested=0
for algorithm in (algorithms.AES,algorithms.SM4):
    for kt,it,ot,enc in itertools.product(range(8),range(8),range(8),(False,True)):
        for header_offset in (16,32):
            cipher=Cipher(algorithm(transform(candidate,kt)),modes.ECB())
            op=cipher.encryptor() if enc else cipher.decryptor()
            plain=transform(op.update(transform(frame[header_offset:header_offset+16],it))+op.finalize(),ot)
            words=struct.unpack('<4I',plain);tested+=1
            if words[0]==0x1cc00 and words[2]&0xffff==0xa104:
                matches.append(dict(algorithm=algorithm.__name__,key_transform=kt,input_transform=it,output_transform=ot,encrypt=enc,header_offset=header_offset,plaintext=plain.hex()))
(OUT/'configuration_candidate.bin').write_bytes(candidate)
report=dict(hardware_access=False,original_flash_sha256=hashlib.sha256(flash).hexdigest(),
    candidate_hex=candidate.hex(),candidate_RAM_address='0x2000021c',candidate_bytes=16,
    candidate_literal_flash_offset=hex(flash.find(candidate)) if candidate in flash else None,
    actual_reset_scatter_reproduced=True,actual_native398_copy_verified=True,
    descriptor_fixture='Only descriptor+4=200007c0 supplied; native398/memcpy executed, no cipher modeled',
    descriptor_configuration_address='0x200007c0',
    header_ciphertexts=[frame[16:32].hex(),frame[32:48].hex()],
    standard_cipher_hypothesis_tests=tested,matching_metadata_hypotheses=matches,
    validation_target='Known START metadata image length1cc00 and hardware IDa104',
    key_confirmed_by_this_header_search=False,IV_identity_confirmed=False,
    dataflow={'START':'Native398 loads2000021c configuration,029c transforms header+32 to20000544 and header+16 to20000554',
              'DATA':'Two16-byte loops load configurations2000021c then20000544; the intermediate result is copied back into the raw DATA buffer before the second pass'},
    limits='This header search identifies an AES-forward metadata match but does not by itself validate the complete format. Full captured-payload and independent physical-source verification is in key_extraction_result.json. The earlier metadata-half assumption was wrong; native header+16 goes to metadata554 and header+32 to file-key544. No brute-force key search performed.')
(OUT/'offline_key_audit.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:v for k,v in report.items() if k not in ('dataflow','header_ciphertexts')},indent=2))
