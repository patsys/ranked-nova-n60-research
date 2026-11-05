"""Exercise final VIA ELF through USB IRQ -> main-loop queue -> VIA -> IN FIFO."""
from pathlib import Path
import sys,struct,json,hashlib,argparse
parser=argparse.ArgumentParser();parser.add_argument('--diagnostic',action='store_true');parser.add_argument('--keymap',choices=['default','neo2'],default='default');parser.add_argument('--rgb',action='store_true');args=parser.parse_args()
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'.tools'))
from unicorn import *
from unicorn.arm_const import *
OUT=ROOT/(('qmk_port/build/firmware_via_diagnostic' if args.diagnostic else 'qmk_port/build/firmware_via')+('_neo2' if args.keymap=='neo2' else ''));OUT=OUT.with_name(OUT.name+'_rgb') if args.rgb else OUT;elf=(OUT/'nova_qmk_research.elf').read_bytes();syms={}
for line in (OUT/'nova_qmk_research.nm').read_text().splitlines():
 p=line.split()
 if len(p)==3:syms[p[2]]=int(p[0],16)
u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
for a,n in [(0,0x20000),(0x20000000,0x10000),(0x40000000,0x20000),(0xe000e000,0x2000)]:u.mem_map(a,n)
phoff=struct.unpack_from('<I',elf,28)[0];phsize,phnum=struct.unpack_from('<HH',elf,42)
for i in range(phnum):
 typ,off,va,pa,fs,ms,flags,align=struct.unpack_from('<8I',elf,phoff+i*phsize)
 if typ==1 and fs:u.mem_write(va,elf[off:off+fs])
writes=[];minimum=syms['__process_stack_end__']
def code(uc,a,s,d):
 global minimum
 minimum=min(minimum,uc.reg_read(UC_ARM_REG_SP))
 if a==syms['nova_platform_delay_original_units']:uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 if a==syms['nova_platform_delay_original_long']:
  uc.reg_write(UC_ARM_REG_R0,1);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
def write(uc,access,a,s,value,data):
 if 0x40000000<=a<0x40020000:writes.append((a,s,value))
u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_WRITE,write)
def put(a,v):u.mem_write(a,struct.pack('<I',v))
def call(name,*args):
 for r,a in zip([UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3],args):u.reg_write(r,a)
 u.reg_write(UC_ARM_REG_SP,syms['__process_stack_end__']);u.reg_write(UC_ARM_REG_LR,0x1ff01)
 u.emu_start(syms[name]|1,0x1ff00,count=2000000)
 assert u.reg_read(UC_ARM_REG_PC)==0x1ff00,name
 return u.reg_read(UC_ARM_REG_R0)
def irq(event):put(0x40016000,event);put(0x40016008,1);call('Vector50')
call('keyboard_init');put(0x40014120,1);assert call('nova_usb_keyboard_init')==1
# Standard SET_CONFIGURATION1 via real SETUP registers and IRQ.
for i,b in enumerate(bytes.fromhex('0009010000000000')):put(0x40017fa0+i*4,b)
irq(0);irq(6)
assert call('ranked_usb_device_configured',syms['device'])==1
cases=[]
def request(name,packet,expected_prefix):
 packet=bytes(packet)+bytes(32-len(packet))
 # Complete prior IN transfer to mark endpoint2 ready.
 irq(10)
 for i,b in enumerate(packet):put(0x40017500+i*4,b)
 put(0x40017f2c,32);irq(13)
 assert bytes(u.mem_read(syms['raw_rx_head'],1))!=bytes(u.mem_read(syms['raw_rx_tail'],1))
 call('nova_usb_keyboard_task')
 assert u.mem_read(syms['raw_tx_pending'],1)==b'\x01'
 start=len(writes);call('nova_usb_keyboard_task');tx=writes[start:]
 data=[value for a,s,value in tx if 0x40017800<=a<0x40017880 and s==4]
 assert len(data)==32,(name,len(data),tx)
 response=bytes(data);assert response.startswith(bytes(expected_prefix)),(name,response.hex(),expected_prefix)
 assert (0x40017ee4,4,32) in tx
 cases.append(dict(name=name,request=packet.hex(),reply=response.hex()))
 return response
request('protocol_v13',[1],[1,0,13])
request('layer_count',[0x11],[0x11,3])
request('read_key_before',[4,0,0,1],[4,0,0,1,0,0x1e])
request('set_key_to_A',[5,0,0,1,0,4],[5,0,0,1,0,4])
request('read_key_after',[4,0,0,1],[4,0,0,1,0,4])
request('oversized_buffer_rejected',[0x12,0,0,29],[0xff])
request('reset_keymap',[6],[6])
request('read_key_reset',[4,0,0,1],[4,0,0,1,0,0x1e])
# Wrong report size must be rejected before VIA parsing.
before=struct.unpack('<I',u.mem_read(syms['nova_via_rx_rejected'],4))[0]
put(0x40017f2c,31);irq(13)
after=struct.unpack('<I',u.mem_read(syms['nova_via_rx_rejected'],4))[0];assert after==before+1
assert minimum>=syms['__process_stack_base__'],hex(minimum)
result=dict(passed=True,elf_sha256=hashlib.sha256(elf).hexdigest(),actual_raw_usb_irq_to_via_to_fifo=True,cases=cases,wrong_length_rejected=True,stack_used=syms['__process_stack_end__']-minimum,fixtures='RAM-like MMIO controller, initializedELFsegments, delays bypassed; actualIRQ/queue/QMKVIA/hostdriver/FIFO code executes',limitations='No physical device/USBhost, persistence or boot acceptance tested')
(ROOT/('qmk_port/via/transport_neo2_rgb_validation.json' if args.rgb else 'qmk_port/via/transport_neo2_validation.json' if args.keymap=='neo2' else 'qmk_port/via/transport_diagnostic_validation.json' if args.diagnostic else 'qmk_port/via/transport_validation.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
print('PASS8 actualVIAUSBqueue roundtrips; wrong-length rejection; stack',result['stack_used'])
