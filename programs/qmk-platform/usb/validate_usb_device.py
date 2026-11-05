"""Build/execute fake-bus C tests and compare native instruction MMIO traces."""
from pathlib import Path
import runpy,subprocess,json,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.tools'))
from unicorn import UC_HOOK_MEM_WRITE,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_PC,UC_ARM_REG_LR
gcc=Path('C:/Strawberry/c/bin/gcc.exe')
out=ROOT/'qmk_port/usb'
subprocess.run([str(gcc),'-std=c11','-Wall','-Wextra','-Werror',str(out/'ranked_usb_io.c'),str(out/'ranked_usb_device.c'),str(out/'test_ranked_usb_device.c'),'-o',str(out/'test_ranked_usb_device.exe')],check=True)
firmware=str(ROOT/'firmware_dump/flash_cpu_pass1.bin')
def host(mode):return subprocess.check_output([str(out/'test_ranked_usb_device.exe'),firmware,mode],text=True)
test_output=host('test').strip()
compiled=json.loads(host('trace'))
runpy.run_path(str(out/'trace_native_control_irq.py'))
native=json.loads((out/'native_control_irq_traces.json').read_text())
comparison=[]
for i,case in enumerate(native):
    for j,stage in enumerate(case['stages']):
        expected=[[w['address'],w['value']] for w in stage['writes']]
        actual=compiled[i][j]
        comparison.append({'name':case['name'],'event':stage['event'],'native':expected,'compiled_c':actual,'equal':expected==actual})
assert all(x['equal'] for x in comparison)
g=runpy.run_path(str(ROOT/'firmware_dump/recover_usb_control_offline.py'))
u=g['prepare']();writes=[];skipped=[]
def code(u,a,s,_):
    if a in (0xf0dc,0xdd80,0xdde8):
        skipped.append(hex(a));u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
def write(u,x,a,s,v,_):
    if 0x40000000<=a<0x40020000:writes.append([hex(a),v])
u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_WRITE,write)
g['run'](u,0x46fc)
compiled_init=json.loads(host('trace_init'))
assert writes==compiled_init,(writes,compiled_init)
u=g['prepare']();descriptor_writes=[];current=[]
def dw(u,x,a,s,v,_):
    if 0x40000000<=a<0x40020000:current.append([hex(a),v])
u.hook_add(UC_HOOK_MEM_WRITE,dw)
for i,b in enumerate(bytes.fromhex('8006000100001200')):u.mem_write(0x40017fa0+4*i,bytes([b,0,0,0]))
for event in [0,6,6,6,7]:
    current.clear();u.mem_write(0x40016000,event.to_bytes(4,'little'))
    if event==7:u.mem_write(0x40017f14,b'\0'*4)
    g['run'](u,0xebf0);descriptor_writes.append(list(current))
compiled_descriptor=json.loads(host('trace_descriptor'))
descriptor_comparison={'native':descriptor_writes,'compiled_c':compiled_descriptor,'equal':descriptor_writes==compiled_descriptor}
(out/'descriptor_irq_comparison.json').write_text(json.dumps(descriptor_comparison,indent=2))
assert descriptor_comparison['equal'],descriptor_comparison
result={'host_tests':test_output,'control_irq_cases':comparison,'controller_init':{'native':writes,'compiled_c':compiled_init,'equal':True,'skipped_native_functions':skipped,'reason':'Platform USB clock enabling and delay timing validated separately; exact controller register ordering remains original'},'hardware_access':False}
result['descriptor_irq']=descriptor_comparison
u=g['prepare']();reset_writes=[]
def rw(u,x,a,s,v,_):
    if 0x40000000<=a<0x40020000 and a!=0x40016008:reset_writes.append([hex(a),v])
u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_WRITE,rw)
u.mem_write(0x40017f58,b'\x08\0\0\0');u.mem_write(0x20001422,b'\x01')
g['run'](u,0xf310)
compiled_reset=json.loads(host('trace_reset'))
assert reset_writes==compiled_reset,(reset_writes,compiled_reset)
result['reset_irq']={'native':reset_writes,'compiled_c':compiled_reset,'equal':True,'source':'Native0xf310 bit3 reset branch, clock anddelay helpers skipped'}
u=g['prepare']();raw_writes=[];raw_reads=[]
def raw_code(u,a,s,_):
    if a==0xcec0:u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
def raw_write(u,x,a,s,v,_):
    if 0x40000000<=a<0x40020000:raw_writes.append([hex(a),v])
def raw_read(u,x,a,s,v,_):
    if 0x40017500<=a<0x40017600:raw_reads.append([hex(a),s])
from unicorn import UC_HOOK_MEM_READ
u.hook_add(UC_HOOK_CODE,raw_code);u.hook_add(UC_HOOK_MEM_WRITE,raw_write);u.hook_add(UC_HOOK_MEM_READ,raw_read)
for i in range(32):u.mem_write(0x40017500+4*i,(0xdeadbe80+i).to_bytes(4,'little'))
u.mem_write(0x40017f2c,(32).to_bytes(4,'little'));u.mem_write(0x40016000,(13).to_bytes(4,'little'))
g['run'](u,0xebf0)
compiled_raw=json.loads(host('trace_raw_out'))
assert raw_writes==compiled_raw,(raw_writes,compiled_raw)
assert raw_reads==[[hex(0x40017500+4*i),1] for i in range(32)]
assert bytes(u.mem_read(0x20001358,32))==bytes(0x80+i for i in range(32))
result['raw_endpoint3_irq']={'native':raw_writes,'compiled_c':compiled_raw,'equal':True,'native_fifo_reads':raw_reads,'native_packet_hex':bytes(u.mem_read(0x20001358,32)).hex(),'skipped_function':'0xcec0 vendor command processing only;originalIRQ/FIFO receive/ack codeexecuted','compiled_host_test':'32bytesep3RX ->copycallback ->ep2TX;32wordFIFOstores andlength32;busycheckandTXcompleteevent10'}
u=g['prepare']();raw_tx=[]
def raw_tx_write(u,x,a,s,v,_):
    if 0x40000000<=a<0x40020000:raw_tx.append([hex(a),v])
u.hook_add(UC_HOOK_MEM_WRITE,raw_tx_write)
u.mem_write(0x20001348,b'\x01\0\0\0');u.mem_write(0x20002000,bytes(0x80+i for i in range(32)))
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2
for reg,v in [(UC_ARM_REG_R0,2),(UC_ARM_REG_R1,0x20002000),(UC_ARM_REG_R2,32)]:u.reg_write(reg,v)
g['run'](u,0xf118)
compiled_tx=json.loads(host('trace_raw_in'))
assert raw_tx==compiled_tx,(raw_tx,compiled_tx)
result['raw_endpoint2_tx']={'native':raw_tx,'compiled_c':compiled_tx,'equal':True,'length':32,'fifo':'0x40017800','length_register':'0x40017ee4'}
# Execute the actual event4 dispatch and class callback, with no function bypass.
u=g['prepare']();event4_writes=[]
def e4write(u,x,a,size,v,_):
    if 0x40000000<=a<0x40020000:event4_writes.append([hex(a),v])
u.hook_add(UC_HOOK_MEM_WRITE,e4write)
for a,v in [(0x40017f78,0x81),(0x40017f7c,0x45),(0x40016000,4),
            (0x20000424,120),(0x20000508,123),(0x2000050c,456),(0x20000528,789)]:
    u.mem_write(a,v.to_bytes(4,'little'))
u.mem_write(0x20001422,bytes([1,5]));u.mem_write(0x20001340,bytes(24))
g['run'](u,0xebf0)
compiled_event4=json.loads(host('trace_event4'))
assert event4_writes==compiled_event4,(event4_writes,compiled_event4)
software={hex(a):int.from_bytes(u.mem_read(a,n),'little') for a,n in
          [(0x20001421,1),(0x20001422,1),(0x20001423,1),(0x2000051c,1),
           (0x2000051d,1),(0x20000528,4),(0x20000424,4),(0x20000508,4),(0x2000050c,4)]}
assert software['0x20001421']==0xa0
for a in ['0x20001422','0x20001423','0x20000528','0x20000424','0x20000508','0x2000050c']:assert software[a]==0
assert software['0x2000051c']==1 and software['0x2000051d']==1
assert bytes(u.mem_read(0x20001340,24))==b'\x01\0\0\0'*6
# Previous implementation's event4 handler acknowledged only. This deliberately
# retains that behavior as a negative control, and must differ from native.
old_event4=[['0x40017eac',16]]
assert old_event4!=event4_writes
result['event4_reset']={'native':event4_writes,'compiled_c':compiled_event4,'equal':True,
    'native_software_memory':software,'native_ready_words':[1]*6,
    'native_functions_skipped':[],'old_ack_only_negative_control_matches':False,
    'physical_event_name':'unverified; raw controller event4',
    'limitation':'RAM-like MMIO model validates instructions and stores, not physical enumeration'}
# Full original IRQ wrapper includes the status ACK and second status read.
u=g['prepare']();outer_writes=[];outer_reads=[]
def ow(u,x,a,size,v,_):
    if 0x40000000<=a<0x40020000:outer_writes.append([hex(a),v])
def ore(u,x,a,size,v,_):
    if a==0x40016008:outer_reads.append(hex(a))
u.hook_add(UC_HOOK_MEM_WRITE,ow);u.hook_add(UC_HOOK_MEM_READ,ore)
for a,v in [(0x40017f78,0x81),(0x40017f7c,0x45),(0x40016000,4),(0x40016008,1)]:u.mem_write(a,v.to_bytes(4,'little'))
g['run'](u,0x312c)
compiled_outer=json.loads(host('trace_event4_outer'))
assert outer_writes==compiled_outer,(outer_writes,compiled_outer)
assert len(outer_reads)==3,outer_reads
result['event4_outer_irq']={'native':outer_writes,'compiled_c':compiled_outer,'equal':True,
    'native_status_reads':len(outer_reads),'source':'actual 0x312c ->0xebf0 ->0x4858; no function bypass',
    'limitation':'Physical MMIO acknowledgement side effects remain outside the memory model'}
aux_cases=[]
for flags in (0,0x80,0x81,0x88):
    u=g['prepare']();aw=[]
    def auxwrite(u,x,a,size,v,_):
        if 0x40000000<=a<0x40020000:aw.append([hex(a),v])
    u.hook_add(UC_HOOK_MEM_WRITE,auxwrite)
    u.mem_write(0x40017f58,flags.to_bytes(4,'little'));u.mem_write(0x20000528,bytes(4))
    g['run'](u,0xf310)
    actual=json.loads(host('trace_aux_'+format(flags,'x')))
    assert aw==actual,(flags,aw,actual)
    aux_cases.append({'flags':flags,'native_bus_flags':0,'native':aw,'compiled_c':actual,'equal':True})
result['aux_bit7_ack']={'cases':aux_cases,'native_functions_skipped':[],
    'unsupported':'Native busflags bit2 timed-resume policy is not implemented; these cases establish busflags0 only'}
(out/'device_validation.json').write_text(json.dumps(result,indent=2))
(out/'control_irq_comparison.json').write_text(json.dumps(comparison,indent=2))
print(test_output)
print('8 control IRQ stages and controller init sequence match native MMIO writes exactly')
