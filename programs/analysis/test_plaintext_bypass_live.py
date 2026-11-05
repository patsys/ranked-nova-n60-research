"""RAM-only plaintext bypass test. No flash writes, erase, or COMPLETE.

Both crypto-on control and crypto-off trials echo all 512 observed source
bytes using diagnostic entry0x6c. They send the same known plaintext page.
"""
from pathlib import Path
import json,struct,hashlib,time,functools
from timing_channel import Channel

OUT=Path('ram_bypass_test'); OUT.mkdir(exist_ok=True)
specs=json.loads(Path('readonly_stub/ram_bypass/manifest.json').read_text())
expected_hashes={0:'2f55694fc7c118846c0385cecde6060bd3279dbdba034bd66eaf1521da2255a0',1:'569543ab55766b0e04c86a8f81dda6e4969295c4fc3291a1b0f1a9c147528f68'}
plaintext=Path('firmware_dump/application_plaintext_0x2000.bin').read_bytes()[:512]
assert len(plaintext)==512 and plaintext[:8]==bytes.fromhex('501c002011220000')
(OUT/'plaintext_test_page.bin').write_bytes(plaintext)
log=dict(plaintext_sha256=hashlib.sha256(plaintext).hexdigest(),trials=[],no_COMPLETE=True)

def save(): (OUT/'result.json').write_text(json.dumps(log,indent=2))

def send(c,frame):
    for offset in range(0,len(frame),64):
        assert c.h.write(b'\0'+frame[offset:offset+64].ljust(64,b'\0'))==65

try:
    for mode in [1,0]:
        spec=specs[str(mode)]; image=Path(spec['file']).read_bytes()
        assert len(image)==440 and hashlib.sha256(image).hexdigest()==expected_hashes[mode]
        record=dict(crypto_mode=mode,stub_sha256=spec['sha256'],transactions=[]); log['trials'].append(record); save()
        time.sleep(5); c=Channel()
        try:
            c.open(); record['version']=c.version
            record['START']=c.send(image)
            observed=bytearray()
            for seq in range(1,12):
                frame=bytes([2,seq,0,0x73,0,2,1,0x77])+plaintext
                tx=dict(sequence=seq,request_sha256=hashlib.sha256(frame).hexdigest(),replies=[])
                record['transactions'].append(tx); send(c,frame)
                expected_len=8 if seq==10 else 12 if seq==11 else 56
                echo=None; ack=False
                for _ in range(4):
                    reply=bytes(c.h.read(65,100 if echo is not None else 2000))
                    if not reply and echo is not None: break
                    if len(reply)==65 and reply[0]==0: reply=reply[1:]
                    tx['replies'].append(reply.hex()); save()
                    assert len(reply)==64 and reply[:4]==bytes([2,seq,0,0x73]) and reply[6:8]==bytes.fromhex('0177'),tx
                    count=struct.unpack_from('<H',reply,4)[0]
                    if count==expected_len: echo=reply[8:8+count]
                    elif count==1 and reply[8]==4: ack=True
                    else: raise RuntimeError(f'Unexpected reply length/status: {reply.hex()}')
                    if echo is not None and ack: break
                assert echo is not None,tx
                tx['ordinary_ack_received']=ack
                if seq<=10: observed.extend(echo)
                else:
                    source,context,flag=struct.unpack('<III',echo)
                    record['metadata']=dict(source_pointer=hex(source),packet_context=hex(context),ram_crypto_flag=flag,source_is_raw_DATA_buffer=source==context+8)
            assert len(observed)==512
            file=OUT/f'observed_source_crypto_{mode}.bin'; file.write_bytes(observed)
            record.update(observed_file=str(file),observed_sha256=hashlib.sha256(observed).hexdigest(),
                          source_matches_plaintext=bytes(observed)==plaintext,first16_hex=observed[:16].hex())
            assert record['metadata']['ram_crypto_flag']==mode
            if mode==0:
                assert record['source_matches_plaintext'] and record['metadata']['source_is_raw_DATA_buffer']
            else:
                assert not record['source_matches_plaintext']
            print(json.dumps({k:v for k,v in record.items() if k not in ['transactions','version','START']}),flush=True)
        finally:
            record['cleanup']=c.close(); save()
        assert record['cleanup']['application_collections']==6 and record['cleanup']['bootloader_interfaces']==0
    log['plaintext_bypass_verified_without_programming']=True; save()
except Exception as error:
    log['error']=str(error); save(); raise
