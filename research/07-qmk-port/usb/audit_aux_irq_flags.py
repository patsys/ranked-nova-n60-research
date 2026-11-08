"""Read-only native instruction audit; ordinary-memory MMIO, no device access."""
from pathlib import Path
import sys,runpy,json
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.tools'))
from unicorn import UC_HOOK_MEM_WRITE
G=runpy.run_path(str(ROOT/'firmware_dump/recover_usb_control_offline.py'));results=[]
for flags in [0,0x80,0x81,0x88]:
    u=G['prepare']();writes=[]
    def w(u,x,a,n,v,_):
        if 0x40000000<=a<0x40020000:writes.append([hex(a),v])
    u.hook_add(UC_HOOK_MEM_WRITE,w)
    u.mem_write(0x40017f58,flags.to_bytes(4,'little'));u.mem_write(0x20000528,bytes(4))
    G['run'](u,0xf310)
    expected=[] if flags==0 else [['0x40017f58',128]]
    assert writes==expected,(flags,writes)
    results.append({'flags':hex(flags),'native_writes':writes,'pre_fix_c_writes':[], 'equal':not writes})
(ROOT/'qmk_port/usb/aux_irq_missing_bit7.json').write_text(json.dumps({'hardware_access':False,'native_function':'0xf310','native_functions_skipped':[],'native_bus_flags':0,'cases':results},indent=2))
print('Native auxiliary bit7 acknowledgement missing from current C: three cases; zero-flags negative control passes')
