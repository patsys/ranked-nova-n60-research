"""Read-only physical VIA queries; no remap/reset/boot commands."""
from pathlib import Path
import sys,json,argparse
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'.tools'))
import hid

def run():
 devices=[d for d in hid.enumerate(0x3532,0xa0a3) if d['usage_page']==0xff60 and d['usage']==0x61]
 assert len(devices)==1,'Expected exactly one QMK VIA raw interface'
 h=hid.device();result=dict(kind='Read-only VIA query check',queries=[])
 try:
  h.open_path(devices[0]['path'])
  for name,command,prefix in [('protocol',[1],[1,0,13]),('layers',[0x11],[0x11,3]),('base_key_1',[4,0,0,1],[4,0,0,1,0,0x1e])]:
   packet=bytes(command).ljust(32,b'\0');assert h.write(b'\0'+packet)==33
   reply=bytes(h.read(33,2000))
   if len(reply)==33 and reply[0]==0:reply=reply[1:]
   result['queries'].append(dict(name=name,request_hex=packet.hex(),reply_hex=reply.hex()))
   assert len(reply)==32 and reply.startswith(bytes(prefix)),result['queries'][-1]
  result['passed']=True
 finally:h.close()
 (ROOT/'qmk_flash/via_live_queries.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
 print(json.dumps(result,indent=2))
if __name__=='__main__':run()
