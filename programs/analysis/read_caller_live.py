"""Read four caller bytes by calibrated nibble timing; START only."""
import json,time,argparse
from pathlib import Path
from timing_channel import Channel,probe,CODE_WINDOWS

parser=argparse.ArgumentParser()
parser.add_argument('--start',type=lambda s:int(s,0),default=0x101e)
parser.add_argument('--length',type=int,default=4)
args=parser.parse_args()
assert 1<=args.length<=16 and any(lo<=args.start and args.start+args.length<=hi for lo,hi in CODE_WINDOWS)
start_address=f'0x{args.start:08x}'
path=Path('caller_readback_live.json' if args.start==0x101e and args.length==4 else f'caller_{args.start:08x}_{args.length}_live.json')
log=json.loads(path.read_text()) if path.exists() else dict(start_address=start_address,byte_count=args.length,sessions=[])
plan=[('cal',0,False),('cal',8,False)]+[('byte',a,h) for a in range(args.start,args.start+args.length) for h in [False,True]]+[('byte',args.start,False),('byte',args.start,True),('cal',8,False),('cal',0,False)]
builds={p:probe(*p) for p in dict.fromkeys(plan)}

def save(): path.write_text(json.dumps(log,indent=2))
def decode(t):
    zero=log['sessions'][0]['post_write_ms']
    unit=(log['sessions'][1]['post_write_ms']-zero)/8
    assert unit>10
    estimate=(t-zero)/unit
    digit=round(estimate)
    assert 0<=digit<=15 and abs(estimate-digit)<.25,(estimate,digit)
    return dict(value=digit,estimate=estimate,residual_units=abs(estimate-digit))

try:
    for index,p in enumerate(plan):
        if index<len(log['sessions']) and log['sessions'][index].get('complete'): continue
        if index<len(log['sessions']):
            assert 'reply_hex' not in log['sessions'][index]
            log['sessions'].pop()
        assert len(log['sessions'])==index
        blob,spec=builds[p]
        record=dict(index=index,spec=spec)
        log['sessions'].append(record)
        save()
        time.sleep(5)
        c=Channel()
        try:
            c.open()
            record['version']=c.version
            record.update(c.send(blob))
        finally:
            record['final_state']=c.close()
            save()
        assert record['final_state']['application_collections'] and record['final_state']['bootloader_interfaces']==0
        if p[0]=='byte': record['decoded']=decode(record['post_write_ms'])
        record['complete']=True
        save()
        print(json.dumps(dict(probe=spec['name'],ms=round(record['post_write_ms'],3),decoded=record.get('decoded'))),flush=True)
    end=2+args.length*2
    digits=[r['decoded']['value'] for r in log['sessions'][2:end]]
    recovered=bytes(digits[i]|digits[i+1]<<4 for i in range(0,len(digits),2))
    assert [r['decoded']['value'] for r in log['sessions'][end:end+2]]==digits[:2]
    z0=log['sessions'][0]['post_write_ms']; u0=(log['sessions'][1]['post_write_ms']-z0)/8
    z1=log['sessions'][-1]['post_write_ms']; u1=(log['sessions'][-2]['post_write_ms']-z1)/8
    assert abs(u1/u0-1)<.05 and abs(z1-z0)<3
    log['result']=dict(start_address=start_address,hex=recovered.hex(),repeated_first_byte_matches=True,initial_unit_ms=u0,final_unit_ms=u1)
    Path(f'caller_{args.start:04x}.bin').write_bytes(recovered)
    save()
    print(json.dumps(log['result']),flush=True)
except Exception as error:
    log['error']=str(error)
    save()
    raise
