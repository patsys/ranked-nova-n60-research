"""Calibrated full-byte timing read; verifies an already-known byte first."""
import argparse,json,time
from pathlib import Path
from timing_channel import Channel,probe,CODE_WINDOWS

parser=argparse.ArgumentParser()
parser.add_argument('--start',type=lambda s:int(s,0),required=True)
parser.add_argument('--length',type=int,required=True)
args=parser.parse_args()
assert 1<=args.length<=16 and any(lo<=args.start and args.start+args.length<=hi for lo,hi in CODE_WINDOWS)
path=Path(f'fast_code_{args.start:08x}_{args.length}_live.json')
log=json.loads(path.read_text()) if path.exists() else dict(start=args.start,length=args.length,sessions=[])
plan=[('cal',0),('cal',255),('byte',0x1020)]+[('byte',a) for a in range(args.start,args.start+args.length)]+[('byte',args.start),('cal',255),('cal',0)]

def save(): path.write_text(json.dumps(log,indent=2))
def decode(t,z,unit):
    assert unit>2
    estimate=(t-z)/unit; value=round(estimate)
    assert 0<=value<=255 and abs(estimate-value)<.28,(estimate,value)
    return dict(value=value,estimate=estimate,residual_units=abs(estimate-value))

try:
    for index,p in enumerate(plan):
        if index<len(log['sessions']) and log['sessions'][index].get('complete'): continue
        if index<len(log['sessions']):
            assert 'reply_hex' not in log['sessions'][index]
            log['sessions'].pop()
        assert len(log['sessions'])==index
        blob,spec=probe(*p,bits=15,whole=True)
        record=dict(index=index,spec=spec); log['sessions'].append(record); save(); time.sleep(5)
        c=Channel()
        try:
            c.open(); record['version']=c.version; record.update(c.send(blob))
        finally:
            record['final_state']=c.close(); save()
        assert record['final_state']['application_collections'] and not record['final_state']['bootloader_interfaces']
        if p[0]=='byte':
            z=log['sessions'][0]['post_write_ms']; unit=(log['sessions'][1]['post_write_ms']-z)/255
            record['decoded']=decode(record['post_write_ms'],z,unit)
            if index==2: assert record['decoded']['value']==0x33,'Known-byte validation failed'
        record['complete']=True; save()
        print(json.dumps(dict(probe=spec['name'],ms=round(record['post_write_ms'],3),decoded=record.get('decoded'))),flush=True)
    z0=log['sessions'][0]['post_write_ms']; u0=(log['sessions'][1]['post_write_ms']-z0)/255
    z1=log['sessions'][-1]['post_write_ms']; u1=(log['sessions'][-2]['post_write_ms']-z1)/255
    assert abs(u1/u0-1)<.0015 and abs(z1-z0)<1,'Full-byte calibration drift'
    z=(z0+z1)/2; unit=(u0+u1)/2
    recovered=bytes(decode(r['post_write_ms'],z,unit)['value'] for r in log['sessions'][3:3+args.length])
    assert decode(log['sessions'][3+args.length]['post_write_ms'],z,unit)['value']==recovered[0]
    log['result']=dict(start=f'0x{args.start:08x}',hex=recovered.hex(),known_byte_validated=True,repeated_first_byte_matches=True,unit_ms=unit)
    Path(f'fast_code_{args.start:08x}.bin').write_bytes(recovered)
    save(); print(json.dumps(log['result']),flush=True)
except Exception as error:
    log['error']=str(error); save(); raise
