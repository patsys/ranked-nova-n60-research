"""Read SP+52: enclosing handler's saved LR, derived from its epilogue."""
import json,time,functools
from pathlib import Path
from timing_channel import Channel,probe

path=Path('saved_lr_readback_live.json')
log=json.loads(path.read_text()) if path.exists() else dict(stack_offset=52,sessions=[])
plan=[('cal',0),('cal',8)]+[('saved',n) for n in range(8)]+[('savedcheck',0),('saved',0),('saved',4),('cal',8),('cal',0)]

def save(): path.write_text(json.dumps(log,indent=2))
def decode(t):
    zero=log['sessions'][0]['post_write_ms']; unit=(log['sessions'][1]['post_write_ms']-zero)/8
    assert unit>10
    estimate=(t-zero)/unit; digit=round(estimate)
    assert 0<=digit<=15 and abs(estimate-digit)<.25,(estimate,digit)
    return dict(value=digit,estimate=estimate,residual_units=abs(estimate-digit))

try:
    for index,p in enumerate(plan):
        if index<len(log['sessions']) and log['sessions'][index].get('complete'): continue
        if index<len(log['sessions']):
            assert 'reply_hex' not in log['sessions'][index]
            log['sessions'].pop()
        assert len(log['sessions'])==index
        blob,spec=probe(*p)
        record=dict(index=index,spec=spec)
        log['sessions'].append(record); save()
        time.sleep(5)
        c=Channel()
        try:
            c.open(); record['version']=c.version; record.update(c.send(blob))
        finally:
            record['final_state']=c.close(); save()
        assert record['final_state']['application_collections'] and not record['final_state']['bootloader_interfaces']
        if p[0]!='cal': record['decoded']=decode(record['post_write_ms'])
        record['complete']=True; save()
        print(json.dumps(dict(probe=spec['name'],ms=round(record['post_write_ms'],3),decoded=record.get('decoded'))),flush=True)
    digits=[r['decoded']['value'] for r in log['sessions'][2:10]]
    value=sum(v<<(4*i) for i,v in enumerate(digits))
    checksum=functools.reduce(int.__xor__,digits,0)
    assert log['sessions'][10]['decoded']['value']==checksum
    assert log['sessions'][11]['decoded']['value']==digits[0]
    assert log['sessions'][12]['decoded']['value']==digits[4]
    z0=log['sessions'][0]['post_write_ms']; u0=(log['sessions'][1]['post_write_ms']-z0)/8
    z1=log['sessions'][-1]['post_write_ms']; u1=(log['sessions'][-2]['post_write_ms']-z1)/8
    assert abs(u1/u0-1)<.05 and abs(z1-z0)<3
    assert value&1,'Saved word not a Thumb pointer'
    log['result']=dict(saved_lr=f'0x{value:08x}',return_address=f'0x{value&~1:08x}',stack_offset=52,checksum=checksum,
                       repeated_digits_match=True,initial_unit_ms=u0,final_unit_ms=u1)
    save(); print(json.dumps(log['result']),flush=True)
except Exception as error:
    log['error']=str(error); save(); raise
