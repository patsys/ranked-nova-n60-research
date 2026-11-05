"""Observe stable QMK identity and read-only VIA replies; no remap/reset."""
from pathlib import Path
from datetime import datetime,timezone
import sys,time,json
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'.tools'))
import hid
manifest=json.loads((ROOT/'qmk_flash/manifest.json').read_text())
out=ROOT/'qmk_flash/runtime_soak.json'
result=dict(kind='Read-only QMK/VIA stability observation',started_at=datetime.now(timezone.utc).isoformat(),
            elf_sha256=manifest['elf_sha256'],body_sha256=manifest['body_sha256'],samples=[],queries=[],seconds=15)
handle=None;start=time.monotonic();next_query=0
try:
    while True:
        elapsed=time.monotonic()-start
        apps=hid.enumerate(0x3532,0xa0a3);boots=hid.enumerate(0x352d,0x1101)
        keys=[d for d in apps if d['usage_page']==1 and d['usage']==6]
        raw=[d for d in apps if d['usage_page']==0xff60 and d['usage']==0x61]
        result['samples'].append(dict(elapsed=elapsed,apps=len(apps),boot=len(boots)))
        assert len(apps)==2 and len(keys)==len(raw)==1 and not boots,'QMK identity changed'
        if handle is None:handle=hid.device();handle.open_path(raw[0]['path'])
        if elapsed>=next_query or elapsed>=15:
            assert handle.write(b'\0'+bytes([1]).ljust(32,b'\0'))==33
            response=bytes(handle.read(33,2000))
            if len(response)==33 and response[0]==0:response=response[1:]
            result['queries'].append(dict(elapsed=elapsed,reply_hex=response.hex()))
            assert len(response)==32 and response[:3]==bytes([1,0,13]),'VIA protocol reply failed'
            next_query=elapsed+5
        if elapsed>=15:break
        time.sleep(.25)
    result['passed']=True
except BaseException as error:
    result.update(passed=False,error=repr(error));raise
finally:
    if handle:handle.close()
    result['elapsed_seconds']=time.monotonic()-start
    out.write_text(json.dumps(result,indent=2))
print(json.dumps({k:v for k,v in result.items() if k not in ('samples','queries')},indent=2))
