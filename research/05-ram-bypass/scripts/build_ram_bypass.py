"""Build diagnostic-only DATA echo stubs with RAM crypto flag 0/1.

No flash operations. The programming entry snapshots up to 56 source bytes
into the USB RAM buffer, queues an IN reply, restores the incoming length,
then returns success to the native handler. All erase/program entries are
otherwise immediate returns. No controller registers are accessed.
"""
import sys,json,struct,hashlib
from pathlib import Path
from timing_channel import BASE,ENTRIES
from keystone import Ks,KS_ARCH_ARM,KS_MODE_THUMB
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_HOOK_MEM_WRITE,UC_HOOK_CODE
from unicorn.arm_const import *

ART=Path('readonly_stub/ram_bypass'); ART.mkdir(exist_ok=True)
ks=Ks(KS_ARCH_ARM,KS_MODE_THUMB)
manifest={}
for mode in [0,1]:
    image=bytearray(b'\x70\x47'*220)
    for offset in ENTRIES: image[offset:offset+4]=b'\x00\x20\x70\x47'
    for offset,target in [(0x13a,0x80),(0x6c,0x140)]:
        code,_=ks.asm(f'b #{BASE+target}',BASE+offset); image[offset:offset+2]=bytes(code)
    init=f'''
        mov r0, lr
        movs r2, #0x10
        lsls r2, #8
        adds r2, #0x21
        cmp r0, r2
        bne init_done
        ldr r0, [sp, #52]
        movs r2, #0x0c
        lsls r2, #8
        adds r2, #0xc3
        cmp r0, r2
        bne init_done
        ldr r0, init_flag
        movs r1, #{mode}
        str r1, [r0]
init_done:
        movs r0, #0
        bx lr
        .align 2
init_flag:
        .word 0x20000214
    '''
    program='''
        push {r1,r2,r3,r4,r5,r6,r7,lr}
        mov r5, r1
        ldrh r6, [r4, #4]
        ldrb r3, [r4, #1]
        cmp r3, #11
        beq metadata
        cmp r3, #0
        beq finished
        cmp r3, #10
        bhi finished
        movs r7, #56
        cmp r3, #10
        bne length_ready
        movs r7, #8
length_ready:
        subs r3, #1
        movs r2, #56
        muls r2, r3, r2
        adds r5, r5, r2
        mov r2, r4
        adds r2, #8
        mov r3, r7
copy:
        ldrb r0, [r5]
        strb r0, [r2]
        adds r5, #1
        adds r2, #1
        subs r3, #1
        bne copy
        b send
metadata:
        movs r7, #12
        ldr r0, [sp]
        str r0, [r4, #8]
        str r4, [r4, #12]
        ldr r0, program_flag
        ldr r0, [r0]
        str r0, [r4, #16]
send:
        mov r1, r7
        strh r1, [r4, #4]
        mov r0, r4
        adds r0, #255
        adds r0, #255
        adds r0, #2
        ldr r0, [r0, #20]
        blx r0
        movs r0, #1
        lsls r0, #18
pause:
        subs r0, #1
        bne pause
        strh r6, [r4, #4]
finished:
        movs r0, #0
        pop {r1,r2,r3,r4,r5,r6,r7,pc}
        .align 2
program_flag:
        .word 0x20000214
    '''
    a,_=ks.asm(init,BASE+0x80); p,_=ks.asm(program,BASE+0x140)
    assert 0x80+len(a)<=0xda and 0x140+len(p)<=440,(len(a),len(p))
    image[0x80:0x80+len(a)]=bytes(a); image[0x140:0x140+len(p)]=bytes(p)
    md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS)
    allowed=['push','pop','b','bx','blx','mov','movs','lsls','ldr','ldrh','ldrb','str','strh','strb','adds','subs','cmp','bne','beq','bhi','muls','nop']
    decoded=list(md.disasm(bytes(a[:-4]),BASE+0x80))+list(md.disasm(bytes(p[:-4]),BASE+0x140))
    assert all(i.mnemonic in allowed for i in decoded),[(i.mnemonic,i.op_str) for i in decoded if i.mnemonic not in allowed]
    cases=0
    for alias in [False,True]:
        for seq in range(1,12):
            uc=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
            uc.mem_map(0,0x2000); uc.mem_map(BASE,0x4000)
            uc.mem_write(BASE,bytes(image)); uc.mem_write(0xa00,bytes.fromhex('7047'))
            context=BASE+0x1000; source=context+8 if alias else BASE+0x1800; sp=BASE+0x3000
            payload=bytes((i*29+7)&255 for i in range(512))
            uc.mem_write(context,bytes([2,seq,0,0x73,0,2,1,0x77])+bytes(512))
            uc.mem_write(source,payload); uc.mem_write(context+0x214,struct.pack('<I',0xa01))
            uc.mem_write(BASE+0x214,struct.pack('<I',mode))
            uc.reg_write(UC_ARM_REG_SP,sp); uc.reg_write(UC_ARM_REG_R1,source); uc.reg_write(UC_ARM_REG_R4,context)
            stop=0x1800; uc.reg_write(UC_ARM_REG_LR,stop|1)
            writes=[]; replies=[]
            uc.hook_add(UC_HOOK_MEM_WRITE,lambda u,access,address,size,value,d:writes.append((address,size)))
            uc.hook_add(UC_HOOK_CODE,lambda u,addr,size,d:replies.append(bytes(u.mem_read(context,64))),begin=0xa00,end=0xa00)
            uc.emu_start((BASE+0x6c)|1,stop,count=600000)
            assert uc.reg_read(UC_ARM_REG_PC)==stop and uc.reg_read(UC_ARM_REG_SP)==sp
            assert uc.reg_read(UC_ARM_REG_R1)==source and uc.reg_read(UC_ARM_REG_R4)==context
            assert struct.unpack('<H',uc.mem_read(context+4,2))[0]==512
            assert len(replies)==1
            count=8 if seq==10 else 12 if seq==11 else 56
            expected=struct.pack('<III',source,context,mode) if seq==11 else payload[(seq-1)*56:(seq-1)*56+count]
            assert replies[0][8:8+count]==expected,(mode,alias,seq)
            assert struct.unpack_from('<H',replies[0],4)[0]==count
            assert all((sp-32<=address and address+size<=sp) or (context+4<=address and address+size<=context+6) or (context+8<=address and address+size<=context+64) for address,size in writes)
            cases+=1
    for valid_lr,valid_saved in [(False,True),(True,False),(True,True)]:
        uc=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS); uc.mem_map(0,0x2000); uc.mem_map(BASE,0x4000)
        uc.mem_write(BASE,bytes(image)); sp=BASE+0x3000
        uc.reg_write(UC_ARM_REG_SP,sp); uc.reg_write(UC_ARM_REG_LR,0x1021 if valid_lr else 0x1201)
        uc.mem_write(sp+52,struct.pack('<I',0xcc3 if valid_saved else 0xaa1)); uc.mem_write(BASE+0x214,struct.pack('<I',99))
        writes=[]; uc.hook_add(UC_HOOK_MEM_WRITE,lambda u,access,address,size,value,d:writes.append((address,size,value)))
        uc.emu_start((BASE+0x13a)|1,0x1020 if valid_lr else 0x1200,count=100)
        assert writes==([(BASE+0x214,4,mode)] if valid_lr and valid_saved else [])
        cases+=1
    name=f'ram_crypto_mode_{mode}'
    (ART/f'{name}.bin').write_bytes(image); (ART/f'{name}.s').write_text(init+'\n/* program at 0x20000140 */\n'+program)
    manifest[str(mode)]=dict(file=str(ART/f'{name}.bin'),sha256=hashlib.sha256(image).hexdigest(),emulated_cases=cases,program_bytes=len(p),init_bytes=len(a))
(ART/'manifest.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps(manifest,indent=2))
