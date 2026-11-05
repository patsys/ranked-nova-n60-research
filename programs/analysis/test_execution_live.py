"""Compare no-store immediate/delayed probes. No firmware or COMPLETE."""
import json
import struct
import functools
import hashlib
import time
import sys
from pathlib import Path
from boot_console import open_bootloader,get_version,hid
from extract_vendor_stub import extract

hashes={'execution_0':'9e9d37eeb754436ca6874f329151b2e0c0c0ec614b32772059b9e54badea70a0',
        'execution_18':'63cffb57f5134c21b5564a4f0ec4f39052172e9d21263fc699e9f10a1ce864fa'}
original,old=extract('fw_update.pcap')
assert len(original)==496 and len(old)==440
results=json.loads(Path('execution_probe_live.json').read_text()) if Path('execution_probe_live.json').exists() else []
results=[r for r in results if 'START' in r]

def exchange(h,frame):
    start=time.perf_counter_ns()
    for pos in range(0,len(frame),64):
        assert h.write(b'\0'+frame[pos:pos+64].ljust(64,b'\0'))==65
    sent=time.perf_counter_ns()
    reply=bytes(h.read(65,2000))
    end=time.perf_counter_ns()
    if len(reply)==65 and reply[0]==0: reply=reply[1:]
    assert len(reply)==64 and reply[:4]==frame[:4] and reply[4:9]==bytes.fromhex('0100017704'),reply.hex()
    return dict(total_ms=round((end-start)/1e6,3),post_write_ms=round((end-sent)/1e6,3),reply_hex=reply.hex())

def leave_transfer(h,record):
    try:
        record['exit_query']=get_version(h)
    except OSError as error:
        record['exit_query_error']=str(error)
    h.close()
    for _ in range(40):
        count=len(hid.enumerate(0x3532,0xa0a3))
        if count: break
        time.sleep(.1)
    record['final_application_collections']=count
    record['final_bootloader_interfaces']=len(hid.enumerate(0x352d,0x1101))
    assert count and not record['final_bootloader_interfaces'],'Did not return to app; stopping'

try:
    for name in ['execution_0','execution_18']:
        if '--repeat' not in sys.argv and any(r['variant']==name and 'DATA' in r for r in results):
            continue
        blob=Path(f'readonly_stub/{name}.bin').read_bytes()
        assert len(blob)==440 and hashlib.sha256(blob).hexdigest()==hashes[name]
        frame=bytearray(original)
        frame[52:492]=blob
        struct.pack_into('<I',frame,492,functools.reduce(int.__xor__,struct.unpack('<110I',blob),0))
        record=dict(variant=name,stub_sha256=hashes[name])
        results.append(record)
        time.sleep(5)  # Application may enumerate before it accepts boot entry.
        h=open_bootloader(True)
        try:
            record['version']=get_version(h)
            record['START']=exchange(h,bytes(frame))
            record['DATA']=exchange(h,bytes.fromhex('0201007300020177')+bytes(512))
        finally:
            leave_transfer(h,record)
        print(json.dumps(record),flush=True)
        time.sleep(2)
finally:
    Path('execution_probe_live.json').write_text(json.dumps(results,indent=2))
