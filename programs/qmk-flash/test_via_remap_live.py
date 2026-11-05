"""Reversible RAM-only VIA remap test in an unpopulated matrix position."""
from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'.tools'))
import hid
manifest=json.loads((ROOT/'qmk_flash/manifest.json').read_text())
result=dict(kind='Reversible VIA remap in physically absent matrix slot',layer=2,row=5,column=0,
            elf_sha256=manifest['elf_sha256'],body_sha256=manifest['body_sha256'],requests=[],restored=False,
            storage='QMK transient EEPROM in RAM; no flash writes')
devices=[d for d in hid.enumerate(0x3532,0xa0a3) if d['usage_page']==0xff60 and d['usage']==0x61]
assert len(devices)==1
h=hid.device();old=None;changed=False
def command(data):
    packet=bytes(data).ljust(32,b'\0');assert h.write(b'\0'+packet)==33
    response=bytes(h.read(33,2000))
    if len(response)==33 and response[0]==0:response=response[1:]
    result['requests'].append(dict(request_hex=packet.hex(),reply_hex=response.hex()))
    assert len(response)==32 and response[:4]==packet[:4]
    return response
def read():return int.from_bytes(command([4,2,5,0])[4:6],'big')
def write(value):
    response=command([5,2,5,0,value>>8,value&255]);assert int.from_bytes(response[4:6],'big')==value
try:
    h.open_path(devices[0]['path']);old=read();result['original']=old
    test=0x68 if old!=0x68 else 0x69;result['test_value']=test
    changed=True;write(test);assert read()==test
    result['remap_readback_passed']=True
except BaseException as error:result['error']=repr(error);raise
finally:
    try:
        if changed:
            write(old);assert read()==old;result['restored']=True
        result['passed']=bool(result.get('remap_readback_passed') and result['restored'])
    finally:
        h.close();(ROOT/'qmk_flash/via_live_remap.json').write_text(json.dumps(result,indent=2))
print(json.dumps({k:v for k,v in result.items() if k!='requests'},indent=2))
