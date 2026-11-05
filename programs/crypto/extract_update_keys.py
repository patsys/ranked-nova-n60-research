"""Offline key recovery and full captured-update plaintext verification.

Uses the verified bootloader's embedded16-byte key and standard AES primitives.
Never opens a device, writes flash or builds an installable update package.
"""
from pathlib import Path
import sys,struct,json,hashlib,functools
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'.tools'))
from extract_vendor_stub import extract
from cryptography.hazmat.primitives.ciphers import Cipher,algorithms,modes
OUT=ROOT/'crypto_research';OUT.mkdir(exist_ok=True)
def sha(data):return hashlib.sha256(data).hexdigest()
def aes_forward(key,data):
    assert len(key)==16 and len(data)%16==0
    c=Cipher(algorithms.AES(key),modes.ECB()).encryptor();return c.update(data)+c.finalize()
def aes_inverse(key,data):
    c=Cipher(algorithms.AES(key),modes.ECB()).decryptor();return c.update(data)+c.finalize()
def xor_words(data):
    assert len(data)%4==0
    return functools.reduce(int.__xor__,struct.unpack('<'+'I'*(len(data)//4),data),0)
flash=(ROOT/'firmware_dump/flash_cpu_pass1.bin').read_bytes()
assert sha(flash)=='5adca278d90a0672e05dfe5ad47d1635242f9ec0ff78827d83d9f28d6ccd8b49'
master=(ROOT/'firmware_dump/boot_initial_ram.bin').read_bytes()[0x21c:0x22c]
assert flash[0x173c:0x174c]==master
start,_=extract(ROOT/'fw_update.pcap')
raw=(ROOT/'fw_update.pcap').read_bytes();assert raw[:4]==bytes.fromhex('d4c3b2a1')
pos=24;reports=[]
while pos<len(raw):
    _,_,size,_=struct.unpack_from('<4I',raw,pos);packet=raw[pos+16:pos+16+size];pos+=16+size
    if len(packet)<27:continue
    header=struct.unpack_from('<H',packet)[0];bus,device=struct.unpack_from('<HH',packet,17)
    length=struct.unpack_from('<I',packet,23)[0];data=packet[header:header+length]
    if bus==1 and device==7 and packet[21]==4 and packet[22]==1 and packet[16]==0 and len(data)==64:reports.append(data)
frames=[];pending=bytearray();expected=0
for report in reports:
    if pending:
        pending.extend(report)
        if len(pending)>=expected:frames.append(bytes(pending[:expected]));pending.clear()
    elif report[3]==0x73 and report[7]==0x77:
        expected=8+struct.unpack_from('<H',report,4)[0]
        if expected<=64:frames.append(report[:expected])
        else:pending.extend(report)
assert not pending
data_frames=[f for f in frames if f[0]==2]
assert len(data_frames)==230 and all(len(f)==520 and f[1]==i+1 for i,f in enumerate(data_frames))
ciphertext=b''.join(f[8:] for f in data_frames);assert len(ciphertext)==0x1cc00
assert ciphertext[:512]==(ROOT/'captured_first_page.bin').read_bytes()
metadata=aes_forward(master,start[16:32]);file_key=aes_forward(master,start[32:48])
length,whole_xor,packed,code_xor=struct.unpack('<4I',metadata)
code_length=(packed>>16)*4;hardware_id=packed&0xffff
assert length==len(ciphertext)==0x1cc00 and hardware_id==0xa104 and code_length==0xe908
intermediate=aes_forward(master,ciphertext)
plaintext=aes_forward(file_key,intermediate)
reference=flash[0x2000:0x2000+len(plaintext)]
assert plaintext[:code_length]==reference[:code_length], 'Executable code mismatch'
assert xor_words(plaintext[:code_length])==code_xor, 'Header executable checksum mismatch'
# Whole-body checksum and inverse reconstruction are additional independent
# validation targets; neither alone establishes physical flash equality.
whole_matches=xor_words(plaintext)==whole_xor
inverse=aes_inverse(master,aes_inverse(file_key,plaintext))
assert inverse==ciphertext
physical_input=(ROOT/'ram_bypass_test/plaintext_test_page.bin').read_bytes()
physical_observed=(ROOT/'ram_bypass_test/observed_source_crypto_1.bin').read_bytes()
physical_prediction=aes_forward(file_key,aes_forward(master,physical_input))
assert len(physical_observed)==512 and physical_prediction==physical_observed
zero_input=bytes(512);zero_prediction=aes_forward(file_key,aes_forward(master,zero_input))
assert all(zero_prediction[i:i+16]==zero_prediction[:16] for i in range(0,512,16))
differences=[i for i,(a,b) in enumerate(zip(plaintext,reference)) if a!=b]
ranges=[]
for i in differences:
    if ranges and ranges[-1][1]==i:ranges[-1][1]=i+1
    else:ranges.append([i,i+1])
for name,data in [('master_key.bin',master),('captured_file_key.bin',file_key),
                  ('captured_header_metadata.bin',metadata),('captured_update_ciphertext.bin',ciphertext),
                  ('captured_update_plaintext.bin',plaintext)]:
    (OUT/name).write_bytes(data)
result=dict(passed=True,hardware_access=False,master_key_hex=master.hex(),master_flash_offset='0x173c',
    master_initial_RAM_address='0x2000021c',captured_file_key_hex=file_key.hex(),
    primitive='AES-128 ECB forward operation; native decryption uses encryption primitive',
    header={'metadata':metadata.hex(),'image_bytes':length,'whole_xor':hex(whole_xor),'hardware_id':hex(hardware_id),'code_bytes':code_length,'code_xor':hex(code_xor)},
    header_rule='metadata=AES_encrypt(master,header[0:16]); file_key=AES_encrypt(master,header[16:32])',
    data_rule='plaintext=AES_encrypt(file_key,AES_encrypt(master,ciphertext))',
    IV_required=False,capture_data_frames=len(data_frames),ciphertext_sha256=sha(ciphertext),plaintext_sha256=sha(plaintext),
    verified_executable_bytes=code_length,executable_matches_original_CPU_dump=True,
    executable_checksum_matches=True,whole_body_checksum_matches=whole_matches,
    inverse_reproduces_all_captured_ciphertext=True,total_CPU_snapshot_differing_bytes=len(differences),
    independent_saved_physical_source_matches=True,independent_physical_bytes=512,
    independent_physical_source_sha256=sha(physical_observed),
    differences_CPU_address_ranges=[{'start':hex(0x2000+a),'end_exclusive':hex(0x2000+b)} for a,b in ranges],
    all_differences_in_vendor_data_region=all(0x2000+i>=0x1a000 for i in differences),
    zero_ciphertext_block_result_hex=aes_forward(file_key,aes_forward(master,bytes(16))).hex(),
    zero_input_predicted_blocks=32,zero_prediction_is_physical_measurement=False,
    limitations='Validated on this captured update and its known executable plaintext. No claim that all products/versions use the same master key. CPU snapshot settings/journal may differ from update-file data. No live zero-block experiment was needed or performed; its value is predicted by the verified offline transform.')
assert result['whole_body_checksum_matches'] and result['all_differences_in_vendor_data_region']
(OUT/'key_extraction_result.json').write_text(json.dumps(result,indent=2))
(OUT/'zero_input_prediction.bin').write_bytes(zero_prediction)
print(json.dumps({k:v for k,v in result.items() if k!='differences_CPU_address_ranges'},indent=2))
