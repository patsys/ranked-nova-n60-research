"""Read incoming LR via START timing. Register-only payload; no DATA/COMPLETE."""
import json,struct,functools,hashlib,time
from pathlib import Path
from boot_console import open_bootloader,get_version,hid
from extract_vendor_stub import extract

manifest=json.loads(Path('readonly_stub/lr_probes.json').read_text())
original,old=extract('fw_update.pcap')
assert len(original)==496
assert struct.unpack_from('<I',original,492)[0]==functools.reduce(int.__xor__,struct.unpack('<110I',old),0)
path=Path('lr_readback_live.json')
log=json.loads(path.read_text()) if path.exists() else dict(method='incoming LR nibble timing; no data-memory accesses',sessions=[])
plan=['cal0','cal8']+[f'lr{i}' for i in range(8)]+['xorcheck','lr0','lr4','cal8','cal0']

def save():
    path.write_text(json.dumps(log,indent=2))

def decode(t):
    zero=log['sessions'][0]['post_write_ms']
    eight=log['sessions'][1]['post_write_ms']
    unit=(eight-zero)/8
    assert unit>10
    estimate=(t-zero)/unit
    value=round(estimate)
    residual=abs(estimate-value)
    assert 0<=value<=15 and residual<.25,(estimate,residual)
    return dict(value=value,estimate=estimate,residual_units=residual,unit_ms=unit)

try:
    for index,name in enumerate(plan):
        if index<len(log['sessions']) and log['sessions'][index].get('complete'):
            continue
        assert len(log['sessions']) in [index,index+1]
        if len(log['sessions'])==index+1:
            assert 'reply_hex' not in log['sessions'][index], 'Partial exchange needs review'
            log['sessions'].pop()
        spec=manifest[name]
        blob=Path(spec['file']).read_bytes()
        assert len(blob)==440 and hashlib.sha256(blob).hexdigest()==spec['sha256']
        frame=bytearray(original)
        frame[52:492]=blob
        struct.pack_into('<I',frame,492,functools.reduce(int.__xor__,struct.unpack('<110I',blob),0))
        record=dict(index=index,probe=name,sha256=spec['sha256'])
        log['sessions'].append(record)
        save()
        time.sleep(5)
        h=open_bootloader(True)
        try:
            record['version']=get_version(h)
            start=time.perf_counter_ns()
            for offset in range(0,len(frame),64):
                assert h.write(b'\0'+bytes(frame[offset:offset+64]).ljust(64,b'\0'))==65
            sent=time.perf_counter_ns()
            reply=bytes(h.read(65,2000))
            end=time.perf_counter_ns()
            if len(reply)==65 and reply[0]==0: reply=reply[1:]
            record.update(total_ms=(end-start)/1e6,post_write_ms=(end-sent)/1e6,reply_hex=reply.hex())
            assert len(reply)==64 and reply[:9]==bytes.fromhex('010000730100017704'),reply.hex()
        finally:
            try: record['exit_query']=get_version(h)
            except OSError as error: record['exit_query_error']=str(error)
            h.close()
            for _ in range(40):
                app_count=len(hid.enumerate(0x3532,0xa0a3))
                if app_count: break
                time.sleep(.1)
            record['final_application_collections']=app_count
            record['final_bootloader_interfaces']=len(hid.enumerate(0x352d,0x1101))
            save()
            assert app_count and record['final_bootloader_interfaces']==0
        if name.startswith('lr') or name=='xorcheck':
            record['decoded']=decode(record['post_write_ms'])
        record['complete']=True
        save()
        print(json.dumps(dict(probe=name,ms=round(record['post_write_ms'],3),decoded=record.get('decoded'))),flush=True)
    digits=[r['decoded']['value'] for r in log['sessions'][2:10]]
    address=sum(v<<(4*i) for i,v in enumerate(digits))
    checksum=functools.reduce(int.__xor__,digits,0)
    assert log['sessions'][10]['decoded']['value']==checksum,'LR XOR check failed'
    assert log['sessions'][11]['decoded']['value']==digits[0]
    assert log['sessions'][12]['decoded']['value']==digits[4]
    initial_unit=(log['sessions'][1]['post_write_ms']-log['sessions'][0]['post_write_ms'])/8
    end_unit=(log['sessions'][13]['post_write_ms']-log['sessions'][14]['post_write_ms'])/8
    assert abs(end_unit/initial_unit-1)<.05,'Calibration slope drift'
    assert abs(log['sessions'][14]['post_write_ms']-log['sessions'][0]['post_write_ms'])<3,'Calibration baseline drift'
    assert address&1,'LR not a Thumb return pointer'
    log['result']=dict(incoming_lr=f'0x{address:08x}',return_instruction_address=f'0x{address&~1:08x}',
                       checksum_nibble=checksum,repeated_digits_match=True,
                       initial_unit_ms=initial_unit,final_unit_ms=end_unit,
                       caveat='START caller return address; not a USB transmit function address')
    save()
    print(json.dumps(log['result']),flush=True)
except Exception as error:
    log['error']=str(error)
    save()
    raise
