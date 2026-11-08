"""Observe source-buffer word for the capture's first ciphertext page.

Own no-store programming stub; no COMPLETE. Sends a captured 512-byte page
twice per session to compare the source data seen by the CPU.
"""
import json,struct,time,hashlib
from pathlib import Path
from timing_channel import Channel
from probe_chunk_buffer import build,data

raw=Path('fw_update.pcap').read_bytes(); pos=24; reports=[]
while pos<len(raw):
    size=struct.unpack_from('<I',raw,pos+8)[0]; p=raw[pos+16:pos+16+size]; pos+=16+size
    if len(p)==91 and p[16]==0 and p[21]==4 and p[22]==1 and struct.unpack_from('<HH',p,17)==(1,7): reports.append(p[27:])
index=next(i for i,r in enumerate(reports) if r[:8]==bytes.fromhex('0201007300020177'))
frame=b''.join(reports[index:index+9])[:520]
payload=frame[8:]
assert len(payload)==512 and payload[:4]==bytes.fromhex('f06d17be')
Path('captured_first_page.bin').write_bytes(payload)
path=Path('source_word_live.json')
log=json.loads(path.read_text()) if path.exists() else dict(payload_sha256=hashlib.sha256(payload).hexdigest(),ciphertext_first_word=payload[:4].hex(),sessions=[])
assert log['payload_sha256']==hashlib.sha256(payload).hexdigest()
plan=[('zero',0,False),('eight',0,False)]+[('read',i,h) for i in range(4) for h in [False,True]]+[('read',0,False),('read',0,True),('eight',0,False),('zero',0,False)]

def save(): path.write_text(json.dumps(log,indent=2))
def decode(t,index):
    zero=log['sessions'][0]['DATA'][index]['post_write_ms']
    unit=(log['sessions'][1]['DATA'][index]['post_write_ms']-zero)/8
    estimate=(t-zero)/unit; digit=round(estimate)
    return dict(value=digit,estimate=estimate,residual_units=abs(estimate-digit),initially_unambiguous=0<=digit<=15 and abs(estimate-digit)<.25)

try:
    for index,(mode,offset,high) in enumerate(plan):
        if index<len(log['sessions']) and log['sessions'][index].get('complete'): continue
        if index<len(log['sessions']):
            assert not log['sessions'][index].get('DATA'),'Review partial live exchange'
            log['sessions'].pop()
        assert len(log['sessions'])==index
        blob,spec=build(0x6c,mode,offset,high)
        record=dict(index=index,spec=spec,DATA=[]); log['sessions'].append(record); save()
        time.sleep(5); c=Channel()
        try:
            c.open(); record['version']=c.version; record['START']=c.send(blob)
            for seq in [1,2]:
                record['DATA'].append(data(c,seq,payload=payload)); save()
        finally:
            record['final_state']=c.close(); save()
        assert record['final_state']['application_collections'] and not record['final_state']['bootloader_interfaces']
        if mode=='read':
            record['decoded']=[decode(r['post_write_ms'],i) for i,r in enumerate(record['DATA'])]
        record['complete']=True; save()
        print(json.dumps(dict(mode=mode,offset=offset,high=high,decoded=record.get('decoded'))),flush=True)
    words=[]
    for seq in range(2):
        z0=log['sessions'][0]['DATA'][seq]['post_write_ms']; u0=(log['sessions'][1]['DATA'][seq]['post_write_ms']-z0)/8
        z1=log['sessions'][-1]['DATA'][seq]['post_write_ms']; u1=(log['sessions'][-2]['DATA'][seq]['post_write_ms']-z1)/8
        assert abs(u1/u0-1)<.05 and abs(z1-z0)<3
        z=(z0+z1)/2; unit=(u0+u1)/2
        digits=[]
        for r in log['sessions'][2:12]:
            estimate=(r['DATA'][seq]['post_write_ms']-z)/unit; digit=round(estimate)
            assert 0<=digit<=15 and abs(estimate-digit)<.25,(seq,r['spec'],estimate)
            digits.append(digit)
        assert digits[8:]==digits[:2],'Repeated source byte changed'
        word=bytes(digits[i]|digits[i+1]<<4 for i in range(0,8,2)); words.append(word.hex())
    log['result']=dict(source_words_hex=words,ciphertext_first_word_hex=payload[:4].hex(),
                       sequences_match=words[0]==words[1],source_equals_ciphertext=[w==payload[:4].hex() for w in words],
                       repeated_first_byte_matches=True,calibration_passed=True)
    save(); print(json.dumps(log['result']),flush=True)
except Exception as error:
    log['error']=str(error); save(); raise
