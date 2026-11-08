"""Decode one register-computed number through calibrated START ACK timing.
No DATA or COMPLETE packets. No arbitrary payload argument.
"""
import json,struct,functools,hashlib,time
from pathlib import Path
from boot_console import open_bootloader,get_version,hid
from extract_vendor_stub import extract

hashes={
 'number_zero':'fca6c8e3d812ad70757702b0bfcd321dd056623a3bc399c8048269f312305f0c',
 'number_unit':'7e428e791418aec34e5a0f0068ffb2fc1839833868a3e416b3f82a352808b0bd',
 'number_computed':'6c708eb3200295bf5d0cf8d5cb0901ab506557c0a9c075590b5f7215ed82992c'}
original,old=extract('fw_update.pcap')
assert len(original)==496
assert struct.unpack_from('<I',original,492)[0]==functools.reduce(int.__xor__,struct.unpack('<110I',old),0)
log=dict(method='START ACK timing, not a returned USB payload byte',sessions=[])
try:
    for name in hashes:
        blob=Path(f'readonly_stub/{name}.bin').read_bytes()
        assert len(blob)==440 and hashlib.sha256(blob).hexdigest()==hashes[name]
        frame=bytearray(original)
        frame[52:492]=blob
        struct.pack_into('<I',frame,492,functools.reduce(int.__xor__,struct.unpack('<110I',blob),0))
        record=dict(variant=name,sha256=hashes[name])
        log['sessions'].append(record)
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
            try:
                record['exit_query']=get_version(h)
            except OSError as error:
                record['exit_query_error']=str(error)
            h.close()
            for _ in range(40):
                app_count=len(hid.enumerate(0x3532,0xa0a3))
                if app_count: break
                time.sleep(.1)
            record['final_application_collections']=app_count
            record['final_bootloader_interfaces']=len(hid.enumerate(0x352d,0x1101))
            assert app_count and record['final_bootloader_interfaces']==0
        print(json.dumps(record),flush=True)
    times={r['variant']:r['post_write_ms'] for r in log['sessions']}
    unit=times['number_unit']-times['number_zero']
    assert unit>10,'Calibration separation too small'
    estimate=(times['number_computed']-times['number_zero'])/unit
    decoded=round(estimate)
    log['decode']=dict(unit_ms=unit,estimate=estimate,number=decoded,
                       residual_units=abs(estimate-decoded))
    assert 0<=decoded<=15 and abs(estimate-decoded)<.25,'Timing decode ambiguous'
    # Deliberately decode first, before comparing with the expected test value.
    log['matches_test_number']=(decoded==7)
    assert log['matches_test_number']
    print(json.dumps(log['decode']),flush=True)
finally:
    Path('number_readback_live.json').write_text(json.dumps(log,indent=2))
