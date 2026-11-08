"""Offline USBPcap chronology for the captured bootloader at bus 1/address 7."""
import json
import struct
from pathlib import Path
from collections import Counter

raw = Path('fw_update.pcap').read_bytes()
assert raw[:4] == bytes.fromhex('d4c3b2a1')
assert struct.unpack_from('<I', raw, 20)[0] == 249
pos = 24
packets = []
number = 0
while pos < len(raw):
    sec, usec, size, original = struct.unpack_from('<4I', raw, pos)
    d = raw[pos+16:pos+16+size]
    assert len(d) == size
    pos += 16 + size
    number += 1
    if len(d) < 27:
        continue
    header = struct.unpack_from('<H', d)[0]
    bus, device = struct.unpack_from('<HH', d, 17)
    data_length = struct.unpack_from('<I', d, 23)[0]
    payload = d[header:header+data_length]
    packets.append(dict(number=number, time=sec+usec/1e6, bus=bus,
                        device=device, endpoint=d[21], transfer=d[22],
                        info=d[16], header=header, data=payload))

reports = [p for p in packets if p['bus'] == 1 and p['device'] == 7
           and p['transfer'] == 1 and len(p['data']) == 64
           and ((p['endpoint'] == 4 and p['info'] == 0)
                or (p['endpoint'] == 0x84 and p['info'] == 1))]
assert reports
origin = reports[0]['time']
events = []
pending = None
for p in reports:
    d = p['data']
    if p['endpoint'] == 4 and pending:
        pending['data'].extend(d)
        pending['packets'].append(p['number'])
        if len(pending['data']) >= pending['length']:
            frame = bytes(pending['data'][:pending['length']])
            pending['event']['reports'] = len(pending['packets'])
            pending['event']['last_packet'] = p['number']
            pending['event']['payload_bytes'] = len(frame)-8
            pending['event']['body_first16_hex'] = frame[8:24].hex()
            if frame[0] == 3:
                pending['event']['body_hex'] = frame[8:].hex()
            pending = None
        continue
    event = dict(packet=p['number'], seconds=round(p['time']-origin,6),
                 direction='OUT' if p['endpoint'] == 4 else 'IN',
                 first16_hex=d[:16].hex())
    events.append(event)
    if d[3] == 0x73 and d[7] == 0x77:
        event.update(kind={1:'START',2:'DATA',3:'COMPLETE'}.get(d[0],f'OP_{d[0]}'),
                     sequence=d[1], length=struct.unpack_from('<H',d,4)[0])
        if p['endpoint'] == 0x84:
            event['status'] = d[8]
        else:
            total = event['length'] + 8
            if total > 64:
                pending = dict(data=bytearray(d),length=total,event=event,packets=[p['number']])
            else:
                event.update(reports=1,payload_bytes=total-8,body_hex=d[8:total].hex())
    elif b'getv' in d:
        event['kind'] = 'GETV'
    elif b'version:' in d:
        event['kind'] = 'VERSION'
    else:
        event['kind'] = 'OTHER'

assert pending is None
counts = Counter((e['direction'],e['kind']) for e in events)
outs = [e for e in events if e['direction']=='OUT' and e['kind']=='DATA']
ins = [e for e in events if e['direction']=='IN']
summary = dict(packets=number, bootloader_reports=len(reports),
               counts={f'{d} {k}':v for (d,k),v in counts.items()},
               data_payload_bytes=sum(e['payload_bytes'] for e in outs),
               data_sequence_valid=all(e['sequence']==(i+1)%256 for i,e in enumerate(outs)),
               response_statuses=dict(Counter(e['status'] for e in ins if 'status' in e)),
               first_events=events[:6],last_events=events[-6:],
               capture_seconds=round(packets[-1]['time']-packets[0]['time'],3))
Path('upload_capture_chronology.json').write_text(json.dumps(dict(summary=summary,events=events),indent=2))
print(json.dumps(summary,indent=2))
