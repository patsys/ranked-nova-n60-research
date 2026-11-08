"""Exact original 0x312c versus before/fixed C outer IRQ trace comparison.

Only inner event/aux dispatch calls are synthetic callback boundaries. The
actual outer native instructions and actual compiled C dispatcher execute.
"""
from pathlib import Path
import hashlib,json,struct,subprocess,sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'.tools'))
from unicorn import *
from unicorn.arm_const import *
HERE=Path(__file__).resolve().parent;USB=HERE.parent;TOOLS=ROOT/'.build-tools/bin'
flash=(ROOT/'firmware_dump/flash_cpu_pass1.bin').read_bytes()
def sha(data):return hashlib.sha256(data).hexdigest()
def run(args):return subprocess.run([str(x) for x in args],cwd=ROOT,check=True,capture_output=True,text=True).stdout
compiled={}
for name,source in (('before',HERE/'ranked_usb_device_before.c'),('fixed',USB/'ranked_usb_device.c')):
    elf=HERE/(name+'.elf')
    run([TOOLS/'arm-none-eabi-gcc.exe','-mcpu=cortex-m0','-mthumb','-Os','-std=c11','-ffreestanding','-fno-inline',
         '-ffunction-sections','-fdata-sections','-I',USB,'-nostdlib',
         '-Wl,--gc-sections,-Ttext=0x12000,-Tdata=0x20000600,-e,irq_wrapper_test',
         source,USB/'ranked_usb_io.c',HERE/'fixture.c','-Wl,--start-group','-lc','-lgcc','-Wl,--end-group','-o',elf])
    nm=run([TOOLS/'arm-none-eabi-nm.exe','-n',elf]);elf.with_suffix('.nm').write_text(nm)
    symbols={p[2]:int(p[0],16) for line in nm.splitlines() if len(p:=line.split())==3}
    assert 'event_irq' in symbols
    compiled[name]=(elf.read_bytes(),symbols)
def execute(kind,initial,arrival_after_read=0,arrival_bits=0):
    u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
    u.mem_map(0,0x20000);u.mem_map(0x20000000,0x4000);u.mem_map(0x40000000,0x20000)
    if kind=='native':
        u.mem_write(0,flash);entry=0x312c;callbacks={0xebf0:'event',0xf310:'aux'}
    else:
        elf,s=compiled[kind];off=struct.unpack_from('<I',elf,28)[0];size,num=struct.unpack_from('<HH',elf,42)
        for i in range(num):
            typ,p,v,a,n,m,f,align=struct.unpack_from('<8I',elf,off+i*size)
            if typ==1 and n:u.mem_write(v,elf[p:p+n])
        entry=s['irq_wrapper_test'];callbacks={s['event_irq']:'event',s['ranked_usb_device_aux_irq']:'aux'}
    current=[initial];reads=[0];trace=[]
    def memory(uc,access,address,size,value,data):
        if access==UC_MEM_WRITE and address<0x20000:raise AssertionError('Flash write')
        if address!=0x40016008:return
        if access==UC_MEM_READ:
            observed=current[0];uc.mem_write(address,struct.pack('<I',observed));trace.append(['read',observed])
            reads[0]+=1
            # The current LDR observes the pre-arrival word. Future reads/ACKs
            # see the newly latched bit, modeling an independent event arrival.
            if reads[0]==arrival_after_read:current[0]|=arrival_bits
        else:
            trace.append(['ack_write',value])
            # Explicit conditional W0C model, consistent with native masks.
            # This is not a claim that silicon write semantics are documented.
            current[0]&=value
    def code(uc,address,size,data):
        if address in callbacks:
            trace.append(['dispatch',callbacks[address]])
            uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_MEM_READ|UC_HOOK_MEM_WRITE,memory);u.hook_add(UC_HOOK_CODE,code)
    u.reg_write(UC_ARM_REG_SP,0x20001c50);u.reg_write(UC_ARM_REG_LR,0x1ff01)
    u.emu_start(entry|1,0x1ff00,count=50000)
    assert u.reg_read(UC_ARM_REG_PC)==0x1ff00,(kind,hex(u.reg_read(UC_ARM_REG_PC)))
    return {'trace':trace,'status_reads':reads[0],'pending_after':current[0]}
cases=[]
scenarios=[(f'stable_status_{value}',value,0,0) for value in range(4)]
scenarios += [('aux_arrives_after_first_event_test',1,1,2),('event_arrives_after_aux_test',2,2,1),
              ('event_arrives_after_zero_first_test',0,1,1)]
for name,status,after,bits in scenarios:
    observed={kind:execute(kind,status,after,bits) for kind in ('native','before','fixed')}
    assert observed['fixed']==observed['native'],(name,observed)
    if name.startswith('stable_status_') and status:
        assert observed['before']['status_reads']!=observed['native']['status_reads']
    if name=='aux_arrives_after_first_event_test':
        assert ['dispatch','aux'] in observed['native']['trace']
        assert ['dispatch','aux'] not in observed['before']['trace']
    if name=='event_arrives_after_aux_test':
        assert observed['native']['pending_after']==1 and observed['before']['pending_after']==0
    cases.append({'case':name,'initial_status':status,'arrival_after_status_read':after,'arrival_bits':bits,
                  **observed,'exact_fixed_native_match':True})
report={'passed':True,'case_count':len(cases),'cases':cases,
        'native_entry':'0x312c, application vector20=0x312d (external IRQ4)',
        'native_source_sha256':sha(flash),'before_source_sha256':sha((HERE/'ranked_usb_device_before.c').read_bytes()),
        'fixed_source_sha256':sha((USB/'ranked_usb_device.c').read_bytes()),
        'comparison':'Exact ordered status reads, ACK writes, synthetic inner dispatch boundaries and modeled remaining pending bits; before/fixed actual C compiled for Cortex-M0.',
        'limits':'Inner EBF0/F310 callbacks are intercepted only to isolate actual outer dispatcher. Conditional W0C latch model is explicit, not verified silicon semantics. Tests do not establish physical IRQ timing, bus ordering or an actual IRQ storm.'}
(HERE/'outer_irq_validation.json').write_text(json.dumps(report,indent=2)+'\n')
print('PASS: seven exact native/fixed outer IRQ cases; cached version demonstrates two modeled lost-pending-event scenarios.')
