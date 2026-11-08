"""Fixed read-only diagnostic trace capture using an ALREADY OPEN boot reader.

This module never opens/closes a device, resets it, sends DATA/COMPLETE, or
programs flash. CLI modes are offline self-test and saved-file decoding only.
"""
from pathlib import Path
import argparse, hashlib, json, struct, sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'.tools'))
ADDRESS=0x20003000
LENGTH=256
MAGIC=0x4e554442
VERSION=2
SUPPORTED_VERSIONS=(1,2)
CHUNKS=tuple((ADDRESS+offset,min(56,LENGTH-offset)) for offset in range(0,LENGTH,56))
STAGES={1:'start',2:'clock_setup',3:'clock_factory',4:'keyboard_setup',5:'keyboard_init',
        6:'emergency_check',7:'usb_init',8:'irq_enable',9:'main_loop',99:'boot_request'}
REASONS={0:'none',1:'usb_timeout',2:'hardfault',3:'nmi',4:'clock_init',5:'clock_rate',
         6:'matrix_init',7:'emergency_key',8:'usb_init',9:'shared_startup'}
def digest(data):return hashlib.sha256(data).hexdigest()

def decode_trace(data):
    """Decode known 256-byte V1/V2 traces without rewriting stored captures."""
    if len(data)!=LENGTH:return {'signature_valid':False,'error':f'Expected256bytes, received{len(data)}'}
    words=struct.unpack('<64I',data)
    if words[0]!=MAGIC or words[1] not in SUPPORTED_VERSIONS or words[2]!=LENGTH:
        return {'signature_valid':False,'error':'Diagnostic magic/version/length mismatch',
                'observed_header':[hex(value) for value in words[:3]],'raw_words':list(words)}
    names=('magic','version','byte_length','boot_sequence','stage','deadline_ticks','ticks','ever_configured',
           'current_configuration','irq_entries','irq_exits','last_status','last_event','status_reads','event_reads','configuration_changes')
    result=dict(zip(names,words[:16]))
    if words[1]==1:
        result['event_counts']=list(words[16:48])
    else:
        result['event_counts']=list(words[16:45])
        result['shared_startup_status']=words[45]
        result['aux_read_count']=words[46]
        result['last_aux_flags']=words[47]
    result.update(dict(zip(('boot_reason','primask_on_request','ipsr_on_request','exception_number',
                           'exception_return','exception_sp'),words[48:54])))
    result['stacked_frame']=dict(zip(('r0','r1','r2','r3','r12','lr','pc','xpsr'),words[54:62]))
    result['armed'],result['stage_at_boot_request']=words[62:64]
    result['stage_name']=STAGES.get(result['stage'],'unknown')
    result['stage_at_boot_request_name']=STAGES.get(result['stage_at_boot_request'],'unknown')
    result['boot_reason_name']=REASONS.get(result['boot_reason'],'unknown')
    result['irq_entry_minus_exit']=result['irq_entries']-result['irq_exits']
    return {'signature_valid':True,'trace':result}

def _readers():
    from qmk_flash.ram_scan.protocol_build import ram_reader
    images=[(address,count,ram_reader(address,count)) for address,count in CHUNKS]
    assert len(images)==5 and all(len(image)==440 for _,_,image in images)
    assert images[0][0]==ADDRESS and images[-1][0]+images[-1][1]==ADDRESS+LENGTH
    return images

def validate_reader_stubs():
    """Actual native caller ABI, guard failures and original boot retention."""
    from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_HOOK_CODE,UC_HOOK_MEM_WRITE
    from unicorn.arm_const import UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC,UC_ARM_REG_R0,UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_PRIMASK
    flash=(ROOT/'firmware_dump/flash_cpu_pass1.bin').read_bytes()
    assert digest(flash[:0x2000])=='e46c6d9300a13f4d2eea7c16584d24ea6e4e1b83815e5f84f389d4aeb0915f62'
    pattern=bytes((index*31+7)&255 for index in range(LENGTH));cases=[]
    for address,count,image in _readers():
        for mask in (0,1):
            u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
            u.mem_map(0,0x20000);u.mem_write(0,flash);u.mem_map(0x20000000,0x4000)
            u.mem_write(0x20000000,image);u.mem_write(ADDRESS,pattern)
            sp=0x20000a00;ctx=0x20000324;callback=0x20000800
            u.mem_write(sp+36,struct.pack('<5I',ctx,0x55,0x66,0x77,0xcc3))
            u.mem_write(ctx,b'\x01\x00\x00\x73\x01\x00\x01\x77'+bytes(512))
            u.mem_write(ctx+0x214,struct.pack('<I',callback|1));u.mem_write(callback,b'\x70\x47')
            writes=[];replies=[]
            def write(uc,access,a,size,value,data):
                assert ((a in (sp-8,sp-4,sp+52) and size==4) or (a==ctx+4 and size==2) or
                        (ctx+8<=a and a+size<=ctx+8+count and size==1)),(hex(a),size)
                writes.append([a,size])
            def code(uc,a,size,data):
                if a==callback:replies.append(bytes(uc.mem_read(ctx,64)))
            u.hook_add(UC_HOOK_MEM_WRITE,write);u.hook_add(UC_HOOK_CODE,code)
            u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_PRIMASK,mask)
            u.emu_start(0x101d,0xe70,count=5000)
            expected=pattern[address-ADDRESS:address-ADDRESS+count]
            assert u.reg_read(UC_ARM_REG_PC)==0xe70 and u.reg_read(UC_ARM_REG_SP)==sp+56
            assert [u.reg_read(r) for r in (UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7)]==[ctx,0x55,0x66,0x77]
            assert u.reg_read(UC_ARM_REG_PRIMASK)==mask
            assert len(replies)==1 and replies[0][8:8+count]==expected
            assert struct.unpack_from('<H',replies[0],4)[0]==count
            assert bytes(u.mem_read(ADDRESS,LENGTH))==pattern
            cases.append({'address':hex(address),'length':count,'initial_primask':mask,
                          'stub_sha256':digest(image),'bounded_ram_writes':len(writes),'passed':True})
    # Wrong native caller LR or enclosing saved return must not install the tail.
    for label,lr,saved in (('wrong_incoming_lr',0x1051,0xcc3),('wrong_saved_pc',0x1021,0x1235)):
        u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
        u.mem_map(0,0x20000);u.mem_write(0,flash);u.mem_map(0x20000000,0x4000)
        u.mem_write(0x20000000,_readers()[0][2]);sp=0x20000a00
        u.mem_write(sp+52,struct.pack('<I',saved));writes=[]
        u.hook_add(UC_HOOK_MEM_WRITE,lambda uc,access,a,size,value,data:writes.append([a,size,value]))
        u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,lr)
        u.emu_start(0x2000013b,lr&~1,count=1000)
        assert u.reg_read(UC_ARM_REG_PC)==lr&~1 and u.reg_read(UC_ARM_REG_R0)==2 and not writes
        cases.append({'guard_case':label,'no_writes':True,'passed':True})
    # Actual stock scatter/reset/main may rewrite 0..BF0 but must preserve trace.
    u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
    for a,size in ((0,0x20000),(0x10000000,0x1000),(0x20000000,0x4000),(0x40000000,0x20000)):
        u.mem_map(a,size)
    u.mem_write(0,flash);u.mem_write(ADDRESS,pattern)
    metadata=(ROOT/'firmware_dump/boot_safety_audit/metadata_10000600.bin').read_bytes()
    u.mem_write(0x10000600,metadata);u.mem_write(0x4001400c,struct.pack('<I',0x5ac396c5))
    retained=[];ram_writes=[]
    def boot_code(uc,a,size,data):
        if a==0x9bc:uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
        if a==0x848:retained.append(True);uc.emu_stop()
    def boot_write(uc,access,a,size,value,data):
        assert not (ADDRESS<=a<ADDRESS+LENGTH),'Original boot overwrites trace'
        if 0x20000000<=a<0x20004000:ram_writes.append([a,size])
    u.hook_add(UC_HOOK_CODE,boot_code);u.hook_add(UC_HOOK_MEM_WRITE,boot_write)
    u.reg_write(UC_ARM_REG_SP,0x20000bf0);u.emu_start(0x1cd,0,count=100000)
    assert retained and u.reg_read(UC_ARM_REG_PC)==0x848 and bytes(u.mem_read(ADDRESS,LENGTH))==pattern
    return {'passed_native_abi':True,'reader_cases':cases,'no_peripheral_or_flash_writes_by_readers':True,
            'trace_address':hex(ADDRESS),'trace_bytes':LENGTH,'caller_guards_tested':True,
            'original_boot_retention':{'passed':True,'entry':'0x1cd','stopped_at':'0x848','ram_writes':len(ram_writes),
                                       'ram_max_exclusive':hex(max(a+size for a,size in ram_writes))},
            'hardware_access':False,'limits':'Native caller and original boot instructions execute offline; USB TX callback and delay timing are modeled.'}

def read_diagnostic_trace(reader,out_dir):
    """Read fixed trace from existing reader; do not close/reset or inhibit rollback.

    Invalid signature is returned/saved as data, not raised. Transport failures
    save partial evidence and propagate so the rollback caller can handle them.
    Caller must already have verified the bootloader and application preimage.
    """
    from stock_restore.restore_stock import send,receive,start_frame
    channel=getattr(reader,'channel',None)
    if channel is None or getattr(channel,'h',None) is None:raise RuntimeError('An already-open reader is required')
    validation=validate_reader_stubs() # Complete native ABI validation before sending anything.
    out=Path(out_dir);out.mkdir(parents=True,exist_ok=True)
    binary_path=out/'diagnostic_trace.bin';json_path=out/'diagnostic_trace.json'
    data=bytearray();records=[]
    log={'operation':'fixed_read_only_diagnostic_trace','address':hex(ADDRESS),'requested_bytes':LENGTH,
         'device_opened':False,'device_closed':False,'reset_requested':False,'DATA_sent':False,'COMPLETE_sent':False,
         'caller_must_continue_rollback':True,'bin_file':str(binary_path),'json_file':str(json_path),
         'native_validation':validation,'chunks':records}
    def save():
        binary_path.write_bytes(data);log['bytes_read']=len(data);log['sha256']=digest(data)
        json_path.write_text(json.dumps(log,indent=2)+'\n',encoding='utf-8')
    try:
        for address,count,image in _readers():
            send(channel,start_frame(channel,image));reply=receive(channel,1,0,count)
            data.extend(reply[8:8+count]);record={'address':hex(address),'length':count,'stub_sha256':digest(image),'reply_hex':reply.hex()}
            records.append(record)
            if hasattr(reader,'records'):reader.records.append({'diagnostic_trace':record})
        log.update(decode_trace(bytes(data)));log['read_complete']=True;save();return log
    except Exception as error:
        log['read_complete']=False;log['signature_valid']=False;log['transport_error']=repr(error);save();raise

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Offline diagnostic trace tools; no standalone device opening')
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--self-test',action='store_true');mode.add_argument('--decode-file',type=Path)
    args=parser.parse_args()
    if args.self_test:
        validation=validate_reader_stubs()
        example=struct.pack('<64I',MAGIC,1,LENGTH,*range(3,64))
        assert decode_trace(example)['signature_valid'] and decode_trace(example)['trace']['stacked_frame']['pc']==60
        decoded_v1=decode_trace(example)['trace']
        assert len(decoded_v1['event_counts'])==32 and 'aux_read_count' not in decoded_v1 and 'shared_startup_status' not in decoded_v1
        v2_words=list(struct.unpack('<64I',example));v2_words[1]=2;v2_words[45]=0x12345678;v2_words[46]=1234;v2_words[47]=0x88;v2_words[48]=9
        example_v2=struct.pack('<64I',*v2_words);decoded_v2=decode_trace(example_v2)
        assert decoded_v2['signature_valid'] and len(decoded_v2['trace']['event_counts'])==29
        assert decoded_v2['trace']['shared_startup_status']==0x12345678
        assert decoded_v2['trace']['aux_read_count']==1234 and decoded_v2['trace']['last_aux_flags']==0x88
        assert decoded_v2['trace']['boot_reason_name']=='shared_startup'
        assert decoded_v2['trace']['stacked_frame']==decoded_v1['stacked_frame']
        unknown_version=list(v2_words);unknown_version[1]=3
        assert not decode_trace(struct.pack('<64I',*unknown_version))['signature_valid']
        assert not decode_trace(bytes(LENGTH))['signature_valid'] and not decode_trace(example[:-1])['signature_valid']
        validation['decoder_valid_invalid_and_short_cases']=True
        validation['decoder_v1_preserved_and_v2_aux_fields']=True
        validation['unsupported_version_rejected']=True
        # Exercise the actual host helper against an existing fake HID handle.
        # Opening, closing or resetting anything would fail this fixture.
        import tempfile
        images=_readers()
        class FakeHandle:
            def __init__(self,data,fail_at=None):self.data=data;self.fail_at=fail_at;self.index=0;self.pending=bytearray();self.starts=0
            def write(self,packet):
                assert len(packet)==65 and packet[0]==0
                self.pending.extend(packet[1:]);return 65
            def read(self,length,timeout):
                address,count,image=images[self.index]
                assert self.pending[0]==1 and self.pending[52:492]==image
                self.pending.clear();self.starts+=1
                if self.index==self.fail_at:raise RuntimeError('Injected read failure')
                offset=address-ADDRESS;self.index+=1
                return bytes([1,0,0,0x73,count,0,1,0x77])+self.data[offset:offset+count]+bytes(56-count)
            def close(self):raise AssertionError('Helper closed the existing HID handle')
        class FakeReader:
            def __init__(self,data,fail_at=None):
                self.channel=type('Channel',(),{})();self.channel.h=FakeHandle(data,fail_at)
                self.channel.original=bytes([1,0,0,0x73,0,2,1,0x77])+bytes(512);self.records=[]
            def open(self):raise AssertionError('Helper opened a reader')
            def close(self):raise AssertionError('Helper reset/closed a reader')
        host_cases=[]
        with tempfile.TemporaryDirectory(prefix='nova_trace_offline_') as temp:
            for name,data in (('valid_header',example),('valid_v2_header',example_v2),('invalid_header',bytes(LENGTH))):
                reader=FakeReader(data);result=read_diagnostic_trace(reader,Path(temp)/name)
                assert result['read_complete'] and result['signature_valid']==(name!='invalid_header')
                assert reader.channel.h.starts==5 and len(reader.records)==5
                assert Path(result['bin_file']).read_bytes()==data
                host_cases.append({'case':name,'five_START_only_reads':True,'reader_not_opened_or_closed':True,'passed':True})
            reader=FakeReader(example,fail_at=2);partial=Path(temp)/'transport_failure'
            try:read_diagnostic_trace(reader,partial)
            except RuntimeError as error:assert str(error)=='Injected read failure'
            else:raise AssertionError('Transport failure did not propagate')
            assert len((partial/'diagnostic_trace.bin').read_bytes())==112
            partial_log=json.loads((partial/'diagnostic_trace.json').read_text())
            assert not partial_log['read_complete'] and partial_log['transport_error']
            host_cases.append({'case':'transport_failure','partial_bytes_saved':112,'error_propagated_for_caller':True,'reader_not_closed':True,'passed':True})
        validation['existing_reader_host_cases']=host_cases
        path=ROOT/'qmk_flash/read_diagnostic_trace_validation.json'
        path.write_text(json.dumps(validation,indent=2)+'\n',encoding='utf-8')
        print('PASS: unchanged native readers/guards/boot retention, V1/V2 decoders and four existing-reader transport cases.')
    else:print(json.dumps(decode_trace(args.decode_file.read_bytes()),indent=2))
