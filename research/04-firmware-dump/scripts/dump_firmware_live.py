"""Double-read CPU-visible 128-KiB flash candidate; no flash writes.

The application base/first vector word was verified live at 0x2000.
The app extent 0x1cc00 is from the captured vendor START metadata.
"""
from pathlib import Path
import json,struct,hashlib,time
from usb_block_reader import BlockReader,MAX_FLASH

OUT=Path('firmware_dump'); OUT.mkdir(exist_ok=True)
manifest=dict(method='CPU-visible memory through own guarded START-only USB block stubs',
              flash_base=0,flash_size=MAX_FLASH,application_base=0x2000,application_size=0x1cc00,
              passes=[],started_unix=time.time())
reader=BlockReader()
try:
    reader.open(); manifest['version']=reader.channel.version
    vectors=reader.read(0x2000,56)
    stack,reset=struct.unpack_from('<II',vectors)
    assert stack==0x20001c50 and reset==0x2211 and reset&1
    manifest['vectors']=dict(stack_pointer=hex(stack),reset_vector=hex(reset),hex=vectors.hex())
    reset_code=reader.read(reset&~1,56)
    manifest['reset_code_hex']=reset_code.hex()
    from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS)
    manifest['reset_disassembly']=[dict(address=hex(i.address),mnemonic=i.mnemonic,operands=i.op_str)
                                    for i in md.disasm(reset_code,reset&~1)]
    assert len(manifest['reset_disassembly'])>=8
    for pass_number in [1,2]:
        target=OUT/f'flash_cpu_pass{pass_number}.bin'
        record=dict(pass_number=pass_number,path=str(target),blocks=[])
        manifest['passes'].append(record)
        with target.open('wb') as stream:
            for address in range(0,MAX_FLASH,0x1000):
                data=reader.read(address,0x1000)
                stream.write(data); stream.flush()
                record['blocks'].append(dict(address=hex(address),length=len(data),sha256=hashlib.sha256(data).hexdigest()))
                (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2))
                if address%0x4000==0 or address+0x1000==MAX_FLASH:
                    print(json.dumps(dict(pass_number=pass_number,bytes_read=address+len(data),total=MAX_FLASH)),flush=True)
        blob=target.read_bytes(); assert len(blob)==MAX_FLASH
        record['sha256']=hashlib.sha256(blob).hexdigest()
    one=(OUT/'flash_cpu_pass1.bin').read_bytes(); two=(OUT/'flash_cpu_pass2.bin').read_bytes()
    manifest['passes_identical']=one==two
    if one!=two:
        different=[i for i,(a,b) in enumerate(zip(one,two)) if a!=b]
        manifest['mismatch_count']=len(different); manifest['first_mismatch_offsets']=[hex(i) for i in different[:64]]
        raise RuntimeError('Flash reads differ; do not label dump verified')
    app=one[0x2000:0x1ec00]
    assert len(app)==0x1cc00 and app[:4]==bytes.fromhex('501c0020')
    boot=one[:0x2000]
    (OUT/'application_plaintext_0x2000.bin').write_bytes(app)
    (OUT/'bootloader_0x0000.bin').write_bytes(boot)
    manifest['application_sha256']=hashlib.sha256(app).hexdigest()
    manifest['bootloader_sha256']=hashlib.sha256(boot).hexdigest()
    manifest['application_vectors']=[hex(v) for v in struct.unpack_from('<16I',app)]
    manifest['known_boot_code_matches']=one[0x101c:0x1022]==bytes.fromhex('fff706f933e0')
    assert manifest['known_boot_code_matches']
    (OUT/'reset_handler.disasm.txt').write_text('\n'.join(f"{r['address']}: {r['mnemonic']} {r['operands']}" for r in manifest['reset_disassembly'])+'\n')
    manifest['verified']=True
except Exception as error:
    manifest['error']=str(error); raise
finally:
    manifest['cleanup']=reader.close(); manifest['finished_unix']=time.time()
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2))
    (OUT/'usb_transactions.json').write_text(json.dumps(reader.records,indent=2))
    print(json.dumps({k:v for k,v in manifest.items() if k in ['verified','passes_identical','application_sha256','bootloader_sha256','error','cleanup']}),flush=True)
