"""Read the verified trampoline literal and caller's common exit, START-only."""
import json,time
from pathlib import Path
from timing_channel import Channel,probe

blocks=[(0x234,4),(0x108a,8)]
path=Path('trace_followup_live.json')
log=json.loads(path.read_text()) if path.exists() else dict(blocks=blocks,sessions=[])
reads=[('byte',a,h) for start,length in blocks for a in range(start,start+length) for h in [False,True]]
plan=[('cal',0,False),('cal',8,False)]+reads+[('cal',8,False),('cal',0,False)]

def save(): path.write_text(json.dumps(log,indent=2))
def decode(t):
    zero=log['sessions'][0]['post_write_ms']; unit=(log['sessions'][1]['post_write_ms']-zero)/8
    assert unit>10
    estimate=(t-zero)/unit; value=round(estimate)
    assert 0<=value<=15 and abs(estimate-value)<.25,(estimate,value)
    return dict(value=value,estimate=estimate,residual_units=abs(estimate-value))

try:
    for index,p in enumerate(plan):
        if index<len(log['sessions']) and log['sessions'][index].get('complete'): continue
        if index<len(log['sessions']):
            assert 'reply_hex' not in log['sessions'][index], 'Review partial live exchange'
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
        if p[0]=='byte': record['decoded']=decode(record['post_write_ms'])
        record['complete']=True; save()
        print(json.dumps(dict(probe=spec['name'],ms=round(record['post_write_ms'],3),decoded=record.get('decoded'))),flush=True)
        data={}
        for r in log['sessions']:
            if r.get('complete') and r['spec']['kind']=='byte':
                data[(r['spec']['value'],r['spec']['high'])]=r['decoded']['value']
        for start,length in blocks:
            if all((a,h) in data for a in range(start,start+length) for h in [False,True]):
                recovered=bytes(data[(a,False)]|data[(a,True)]<<4 for a in range(start,start+length))
                Path(f'trace_{start:08x}.bin').write_bytes(recovered)
                log.setdefault('recovered_blocks',{})[hex(start)]=recovered.hex(); save()
    zero=log['sessions'][0]['post_write_ms']; unit=(log['sessions'][1]['post_write_ms']-zero)/8
    endzero=log['sessions'][-1]['post_write_ms']; endunit=(log['sessions'][-2]['post_write_ms']-endzero)/8
    assert abs(endunit/unit-1)<.05 and abs(endzero-zero)<3
    log['calibration_valid']=True; save()
    print(json.dumps(dict(recovered_blocks=log['recovered_blocks'],calibration_valid=True)),flush=True)
except Exception as error:
    log['error']=str(error); save(); raise
