"""Explicit read-only sensor snapshots from the running diagnostic firmware."""
from pathlib import Path
from datetime import datetime, timezone
import sys, json, time, argparse
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from crypto_research.via_state import hid, transfer

def main(seconds):
    assert 1 <= seconds <= 180
    devices = hid.enumerate(0x3532,0xa0a3)
    raw = [d for d in devices if d['usage_page']==0xff60 and d['usage']==0x61]
    assert len(devices)==2 and len(raw)==1 and not hid.enumerate(0x352d,0x1101)
    h=hid.device(); h.open_path(raw[0]['path'])
    out=Path(__file__).parent/datetime.now(timezone.utc).strftime('sensors_%Y%m%dT%H%M%S_%fZ.json')
    result=dict(kind='Read-only running-firmware sensor snapshots',flash_writes=False,captures=[])
    began=time.monotonic()
    try:
        while time.monotonic()-began < seconds:
            banks=[]
            for bank in range(6):
                r=transfer(h,[2,0x80,bank])
                assert r[:5]==bytes([2,0x80,bank,1,1]),'Sensor query not supported or matrix not initialized'
                banks.append(dict(samples=[int.from_bytes(r[i:i+2],'big') for i in range(8,30,2)],raw_row=int.from_bytes(r[6:8],'big'),debounced_row=int.from_bytes(r[30:32],'big')))
            elapsed=round(time.monotonic()-began,2)
            result['captures'].append(dict(seconds=elapsed,banks=banks))
            out.write_text(json.dumps(result,indent=2))
            print(json.dumps(dict(seconds=elapsed,K_L_Odia=banks[2]['samples'][8:11],active=[[b,c] for b,x in enumerate(banks) for c in range(11) if x['raw_row']&(1<<c)])),flush=True)
            time.sleep(0.5)
        result['passed_capture']=True
    finally:
        h.close();out.write_text(json.dumps(result,indent=2))
    print(json.dumps(dict(result_file=str(out),passed_capture=True)),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--seconds',type=int,default=90);a=p.parse_args();main(a.seconds)
