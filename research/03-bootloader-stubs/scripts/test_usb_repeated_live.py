"""Verify changing custom bytes over repeated STARTs in one HID session."""
import json,struct,hashlib,functools
from pathlib import Path
from timing_channel import Channel

def request(c,blob,expected=None):
    assert len(blob)==440
    frame=bytearray(c.original); frame[52:492]=blob
    struct.pack_into('<I',frame,492,functools.reduce(int.__xor__,struct.unpack('<110I',blob),0))
    for offset in range(0,len(frame),64):
        assert c.h.write(b'\0'+bytes(frame[offset:offset+64]).ljust(64,b'\0'))==65
    reply=bytes(c.h.read(65,2000))
    if len(reply)==65 and reply[0]==0: reply=reply[1:]
    record=dict(hex=reply.hex(),stub_sha256=hashlib.sha256(blob).hexdigest())
    assert len(reply)==64 and reply[:8]==bytes.fromhex('0100007301000177'),record
    record['number']=reply[8]
    if expected is not None: assert record['number']==expected,record
    return record

if __name__=='__main__':
    hashes={42:'ce6de346869ebb3d6eac22bdf6e9984b9cd542fb213d917e3ac0764994bf9d5b',
            43:'fe41f84b2339bc9bf24d232d1396f2a1b9d297995d2c2d5c74dd0b825b762b9b'}
    c=Channel(); log=dict(replies=[])
    try:
        c.open(); log['version']=c.version
        for value in [43,42,43]:
            name='usb_number' if value==42 else f'usb_number_{value}'
            blob=Path(f'readonly_stub/{name}.bin').read_bytes()
            assert hashlib.sha256(blob).hexdigest()==hashes[value]
            record=request(c,blob,value); log['replies'].append(record)
            print(json.dumps(record),flush=True)
        log['verified']=True
    except Exception as error:
        log['error']=str(error); raise
    finally:
        log['final_state']=c.close()
        Path('usb_repeated_live.json').write_text(json.dumps(log,indent=2))
