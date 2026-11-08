"""Known-marker DATA test. Own no-store code; no firmware or COMPLETE.

First calibrates only the inferred programming entry, then reads the same
source pointer the original programmer dereferences. If calibration fails,
no pointer-read probe is sent. Only two 512-byte synthetic chunks per trial.
"""
import sys,json,time,hashlib,struct,functools
from pathlib import Path
from timing_channel import Channel,BASE,ENTRIES,ARTIFACTS
from keystone import Ks,KS_ARCH_ARM,KS_MODE_THUMB
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_HOOK_MEM_WRITE,UC_HOOK_CODE
from unicorn.arm_const import *

ks=Ks(KS_ARCH_ARM,KS_MODE_THUMB)
path=Path('chunk_buffer_live.json')
log=json.loads(path.read_text()) if path.exists() else dict(experiments=[])

def build(entry,mode,offset=0,high=False):
    assert entry in [0x6c,0xfc] and mode in ['zero','eight','read']
    assert 0<=offset<8
    blob=bytearray(b'\x70\x47'*220)
    for entry_offset in ENTRIES: blob[entry_offset:entry_offset+4]=b'\x00\x20\x70\x47'
    branch,_=ks.asm('b #0x20000160',BASE+entry)
    blob[entry:entry+2]=bytes(branch)
    if mode=='read':
        # The original 0x6c takes source in R1; 0xfc takes source in R0.
        expression=('mov r0, r1; ' if entry==0x6c else '')+f'ldrb r0, [r0, #{offset}]; '
        if high: expression+='lsrs r0, #4; '
        expression+='lsls r0, #28; lsrs r0, #28; '
    else: expression=f'movs r0, #{8 if mode=="eight" else 0}; '
    expression+='''
        cmp r0, #0
        beq done
        lsls r0, #18
    again:
        subs r0, #1
        bne again
    done:
        movs r0, #0
        bx lr
    '''
    code,_=ks.asm(expression,BASE+0x160)
    blob[0x160:0x160+len(code)]=bytes(code)
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS)
    instructions=list(md.disasm(bytes(blob),BASE))
    assert sum(i.size for i in instructions)==440
    assert all(i.mnemonic in ['b','bx','mov','movs','ldrb','lsls','lsrs','cmp','beq','subs','bne'] for i in instructions)
    cmp_pc=next(i.address for i in instructions if i.mnemonic=='cmp')
    for called in ENTRIES:
        for marker in [0xa5,0x5a]:
            uc=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
            uc.mem_map(BASE,0x2000); uc.mem_write(BASE,bytes(blob))
            source=BASE+0x1000; uc.mem_write(source,bytes([marker])*512)
            uc.reg_write(UC_ARM_REG_R0,source if entry==0xfc else 0)
            uc.reg_write(UC_ARM_REG_R1,source)
            stop=BASE+0x1800; uc.reg_write(UC_ARM_REG_LR,stop|1)
            writes=[]; sampled=[]
            uc.hook_add(UC_HOOK_MEM_WRITE,lambda *args:writes.append(args))
            uc.hook_add(UC_HOOK_CODE,lambda u,a,s,d:sampled.append(u.reg_read(UC_ARM_REG_R0)),begin=cmp_pc,end=cmp_pc)
            uc.emu_start((BASE+called)|1,stop,count=8500000)
            assert uc.reg_read(UC_ARM_REG_PC)==stop and not writes and uc.reg_read(UC_ARM_REG_R0)==0
            expected=((marker>>4 if high else marker&15) if mode=='read' else 8 if mode=='eight' else 0)
            assert sampled==([expected] if called==entry else [])
    stem=f'chunk_{entry:03x}_{mode}_{offset}_{int(high)}'
    ARTIFACTS.mkdir(parents=True,exist_ok=True)
    (ARTIFACTS/f'{stem}.bin').write_bytes(blob)
    (ARTIFACTS/f'{stem}.s').write_text(expression)
    (ARTIFACTS/f'{stem}.disasm.txt').write_text('\n'.join(f'{i.address:08x}: {i.mnemonic} {i.op_str}' for i in instructions))
    return bytes(blob),dict(entry=hex(entry),mode=mode,offset=offset,high=high,sha256=hashlib.sha256(blob).hexdigest(),emulated_calls=12)

def data(c,seq,marker=None,payload=None):
    if payload is None: payload=bytes([marker])+bytes(511)
    assert len(payload)==512
    frame=bytes([2,seq,0,0x73,0,2,1,0x77])+payload
    start=time.perf_counter_ns()
    for offset in range(0,len(frame),64):
        assert c.h.write(b'\0'+frame[offset:offset+64].ljust(64,b'\0'))==65
    sent=time.perf_counter_ns(); reply=bytes(c.h.read(65,2000)); end=time.perf_counter_ns()
    if len(reply)==65 and reply[0]==0: reply=reply[1:]
    record=dict(sequence=seq,marker=marker,payload_sha256=hashlib.sha256(payload).hexdigest(),total_ms=(end-start)/1e6,post_write_ms=(end-sent)/1e6,reply_hex=reply.hex())
    assert len(reply)==64 and reply[:9]==bytes([2,seq,0,0x73,1,0,1,0x77,4]),record
    return record

def trial(entry,mode):
    blob,spec=build(entry,mode)
    record=dict(spec=spec,DATA=[]); log['experiments'].append(record)
    path.write_text(json.dumps(log,indent=2)); time.sleep(5)
    c=Channel()
    try:
        c.open(); record['version']=c.version; record['START']=c.send(blob)
        for seq,marker in [(1,0xa5),(2,0x5a)]:
            record['DATA'].append(data(c,seq,marker))
            path.write_text(json.dumps(log,indent=2))
    finally:
        record['final_state']=c.close(); path.write_text(json.dumps(log,indent=2))
    assert record['final_state']['application_collections'] and not record['final_state']['bootloader_interfaces']
    print(json.dumps(record),flush=True)
    return record

def main():
 try:
    for entry in [0x6c,0xfc]:
        baseline=trial(entry,'zero'); eight=trial(entry,'eight')
        units=[(eight['DATA'][i]['post_write_ms']-baseline['DATA'][i]['post_write_ms'])/8 for i in range(2)]
        if not all(10<u<60 for u in units):
            log.setdefault('entry_not_confirmed',[]).append(hex(entry)); continue
        result=trial(entry,'read')
        decoded=[]
        for i,expected in enumerate([5,10]):
            estimate=(result['DATA'][i]['post_write_ms']-baseline['DATA'][i]['post_write_ms'])/units[i]
            value=round(estimate)
            assert 0<=value<=15 and abs(estimate-value)<.25,(estimate,value)
            decoded.append(dict(value=value,estimate=estimate,expected=expected,matches=value==expected))
        log['result']=dict(entry=hex(entry),units_ms=units,decoded=decoded,markers_match=all(r['matches'] for r in decoded))
        print(json.dumps(log['result']),flush=True)
        break
    else:
        log['result']=dict(markers_match=False,reason='Neither inferred programming entry showed calibration timing')
 except Exception as error:
    log['error']=str(error); raise
 finally:
    path.write_text(json.dumps(log,indent=2))

if __name__=='__main__': main()
