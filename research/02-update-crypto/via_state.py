"""Preserve volatile VIA configuration across a research bootloader session.

Backup only reads. Restore writes only differences to the transient RAM backend
and verifies readback. Do not print macro or keymap contents.
"""
from pathlib import Path
import sys,json,hashlib,argparse
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'.tools'))
import hid
def sha(b):return hashlib.sha256(b).hexdigest()
def transfer(h,packet):
    packet=bytes(packet).ljust(32,b'\0');assert len(packet)==32
    assert h.write(b'\0'+packet)==33
    response=bytes(h.read(33,2000))
    if len(response)==33 and response[0]==0:response=response[1:]
    assert len(response)==32 and response[0]==packet[0], 'Unexpected VIA reply'
    return response
def get_buffer(h,command,size):
    data=bytearray()
    for off in range(0,size,28):
        count=min(28,size-off);header=[command,off>>8,off&255,count]
        reply=transfer(h,header);assert reply[:4]==bytes(header)
        data.extend(reply[4:4+count])
    return bytes(data)
def set_buffer(h,command,data):
    for off in range(0,len(data),28):
        chunk=data[off:off+28];header=bytes([command,off>>8,off&255,len(chunk)])
        reply=transfer(h,header+chunk);assert reply[:4]==header
def run(folder,restore=False):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    devices=hid.enumerate(0x3532,0xa0a3)
    raw=[d for d in devices if d['usage_page']==0xff60 and d['usage']==0x61]
    assert len(devices)==2 and len(raw)==1 and not hid.enumerate(0x352d,0x1101)
    h=hid.device();h.open_path(raw[0]['path'])
    try:
        assert transfer(h,[1])[:3]==bytes([1,0,13])
        layers=transfer(h,[0x11])[1];assert layers==3
        macro_size=int.from_bytes(transfer(h,[0x0d])[1:3],'big');assert 0<=macro_size<=1024
        layout=transfer(h,[2,2])[2:6]
        buffers={'keymap':get_buffer(h,0x12,3*6*11*2),'macros':get_buffer(h,0x0e,macro_size)}
        path=folder/'via_state_manifest.json'
        if not restore:
            assert not path.exists(),'Refuse to overwrite saved VIA state'
            manifest=dict(protocol=13,layers=layers,matrix_rows=6,matrix_cols=11,layout_options_hex=layout.hex(),buffers={},kind='Read-only backup of volatile VIA state')
            for name,data in buffers.items():
                (folder/(name+'.bin')).write_bytes(data)
                manifest['buffers'][name]=dict(file=name+'.bin',bytes=len(data),sha256=sha(data))
            path.write_text(json.dumps(manifest,indent=2));print(json.dumps(manifest,indent=2));return
        manifest=json.loads(path.read_text());changes=[]
        for name,get_id,set_id in [('keymap',0x12,0x13),('macros',0x0e,0x0f)]:
            spec=manifest['buffers'][name];saved=(folder/spec['file']).read_bytes()
            assert len(saved)==spec['bytes']==len(buffers[name]) and sha(saved)==spec['sha256']
            if saved!=buffers[name]:set_buffer(h,set_id,saved);changes.append(name)
            assert get_buffer(h,get_id,len(saved))==saved,'VIA restore readback failed'
        original=bytes.fromhex(manifest['layout_options_hex'])
        if original!=layout:
            transfer(h,bytes([3,2])+original);changes.append('layout_options')
        assert transfer(h,[2,2])[2:6]==original
        result=dict(restored_and_verified=True,changed_buffers=changes,no_flash_writes=True)
        (folder/'via_restore_result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
    finally:h.close()
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('folder');p.add_argument('--restore',action='store_true');a=p.parse_args();run(a.folder,a.restore)
