"""Compare CPU-visible flash after the RAM-only bypass with verified backup."""
from pathlib import Path
import json,hashlib
from usb_block_reader import BlockReader,MAX_FLASH

out=Path('ram_bypass_test'); result_path=out/'result.json'
result=json.loads(result_path.read_text())
assert result['plaintext_bypass_verified_without_programming']
baseline=Path('firmware_dump/flash_cpu_pass1.bin').read_bytes()
assert len(baseline)==MAX_FLASH and hashlib.sha256(baseline).hexdigest()=='5adca278d90a0672e05dfe5ad47d1635242f9ec0ff78827d83d9f28d6ccd8b49'
reader=BlockReader(); record=dict(baseline_sha256=hashlib.sha256(baseline).hexdigest())
try:
    reader.open(); record['version']=reader.channel.version
    observed=bytearray()
    with (out/'flash_after.bin').open('wb') as stream:
        for address in range(0,MAX_FLASH,4096):
            chunk=reader.read(address,4096); observed.extend(chunk); stream.write(chunk); stream.flush()
            if (address+4096)%32768==0:
                print(json.dumps(dict(bytes_read=address+4096,total=MAX_FLASH)),flush=True)
    record['after_sha256']=hashlib.sha256(observed).hexdigest()
    record['byte_length']=len(observed); record['flash_unchanged']=bytes(observed)==baseline
    if not record['flash_unchanged']:
        record['first_differences']=[hex(i) for i,(a,b) in enumerate(zip(observed,baseline)) if a!=b][:64]
    assert record['flash_unchanged'],'Post-test flash differs from baseline; inspect differences'
finally:
    record['cleanup']=reader.close()
    result['flash_verification']=record
    result_path.write_text(json.dumps(result,indent=2))
    (out/'flash_verification_usb.json').write_text(json.dumps(reader.records,indent=2))
    print(json.dumps(record),flush=True)
