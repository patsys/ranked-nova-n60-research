"""One guarded START-only test of native USB status-byte output (42)."""
import json,hashlib,struct,functools,time
from pathlib import Path
from timing_channel import Channel

blob=Path('readonly_stub/usb_number.bin').read_bytes()
assert len(blob)==440 and hashlib.sha256(blob).hexdigest()=='ce6de346869ebb3d6eac22bdf6e9984b9cd542fb213d917e3ac0764994bf9d5b'
log=dict(stub_sha256=hashlib.sha256(blob).hexdigest(),expected_number=42,
         operation='START only; guarded RAM stack return to native status builder',replies=[])
c=Channel()
try:
    c.open(); log['version']=c.version
    frame=bytearray(c.original)
    frame[52:492]=blob
    struct.pack_into('<I',frame,492,functools.reduce(int.__xor__,struct.unpack('<110I',blob),0))
    log['start_frame_sha256']=hashlib.sha256(frame).hexdigest()
    log['writes']=[]
    for offset in range(0,len(frame),64):
        n=c.h.write(b'\0'+bytes(frame[offset:offset+64]).ljust(64,b'\0'))
        log['writes'].append(n)
        assert n==65
    for i in range(3):
        reply=bytes(c.h.read(65,2000 if i==0 else 200))
        if not reply: break
        if len(reply)==65 and reply[0]==0: reply=reply[1:]
        record=dict(hex=reply.hex())
        if len(reply)==64 and reply[:8]==bytes.fromhex('0100007301000177'):
            record['payload_number']=reply[8]
        log['replies'].append(record)
        print(json.dumps(record),flush=True)
    log['verified_usb_number']=any(r.get('payload_number')==42 for r in log['replies'])
    assert log['verified_usb_number'],'Expected number absent from USB payload'
except Exception as error:
    log['error']=str(error)
    raise
finally:
    log['final_state']=c.close()
    Path('usb_number_live.json').write_text(json.dumps(log,indent=2))
    print(json.dumps(dict(verified=log.get('verified_usb_number',False),final_state=log['final_state'])),flush=True)
