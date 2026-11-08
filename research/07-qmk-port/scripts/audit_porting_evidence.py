"""Offline inventory of platform evidence already present in the firmware."""
from pathlib import Path
import sys,json,struct,sqlite3,collections
sys.path.insert(0,str(Path(__file__).resolve().parent/'.tools'))
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS,CS_OP_MEM
from capstone.arm_const import ARM_REG_PC

image=Path('firmware_dump/flash_cpu_pass1.bin').read_bytes()
md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS); md.detail=True; md.skipdata=True
references=collections.defaultdict(list); calls=set()
for start,end in [(0xd0,0x154c),(0x20d8,0x10908)]:
    for ins in md.disasm(image[start:end],start):
        if ins.id==0: continue
        if ins.mnemonic=='bl' and ins.op_str.startswith('#0x'):
            target=int(ins.op_str[1:],16)
            if 0<=target<len(image): calls.add(target)
        if ins.mnemonic!='ldr' or len(ins.operands)!=2: continue
        operand=ins.operands[1]
        if operand.type!=CS_OP_MEM or operand.mem.base!=ARM_REG_PC: continue
        location=((ins.address+4)&~3)+operand.mem.disp
        if not 0<=location<=len(image)-4: continue
        value=struct.unpack_from('<I',image,location)[0]
        if 0x40000000<=value<0x40100000 or 0xe000e000<=value<0xe0010000:
            references[value].append(dict(instruction=f'0x{ins.address:08x}',literal_address=f'0x{location:08x}',
                                          assembly=f'{ins.mnemonic} {ins.op_str}'))
summary=dict(source='verified 128KiB CPU dump; offline only',
             caveat='Linear-disassembly candidate references can include literal/data false positives; confirm control flow before naming a peripheral or pin.',
             candidate_direct_call_targets=len(calls),
             peripheral_literals=[dict(value=f'0x{value:08x}',references=refs) for value,refs in sorted(references.items())])
Path('firmware_dump/porting_evidence.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')

note='''# QMK evidence audit

The existing dump/database is sufficient to continue software reverse
engineering without requiring more material from the user. It is not yet a
finished QMK hardware-support implementation.

Already available: verified bootloader/application CPU binaries; vectors and
startup; a RAM-code execution and USB-read mechanism; native USB transmit
path; DATA transform control and a tested RAM-only plaintext bypass; flash
layout; logical key indices, HID mapping and four-layer remap protocol.

Work to derive from those artifacts: coherent clock/GPIO/timer/USB register
definitions and drivers; physical matrix row/column pins and scan polarity;
RAM budget, startup/linker rules, boot validity checks, and a matching QMK
platform/board implementation. A tested restore writer is still separate.
MCU branding can help match an existing platform, but lack of a chip label
does not prevent continuing register-level analysis of the recovered drivers.

`porting_evidence.json` indexes candidate PC-relative peripheral literal
references and their instruction locations in the dump. This is a starting
index, not a proven physical pin map or a complete function analysis. Every
candidate must be checked against actual control flow; arbitrary 32-bit
words in a firmware binary are not reliable register evidence by themselves.

Prior YC500/Yichip attribution remains unconfirmed. Do not use it as an
established MCU identity, and do not infer total SRAM from the initial SP.
No device access, installation, erase, or programming was performed in this
audit. QMK is not yet built or demonstrated on this keyboard.
'''
Path('firmware_dump/QMK_EVIDENCE_AUDIT.md').write_text(note,encoding='utf-8')
c=sqlite3.connect('ranked_re.db')
c.execute('CREATE TABLE IF NOT EXISTS porting_mmio_candidates (literal_value INTEGER PRIMARY KEY, references_json TEXT NOT NULL, confidence TEXT NOT NULL)')
for value,refs in references.items():
    c.execute('INSERT OR REPLACE INTO porting_mmio_candidates VALUES (?,?,?)',(value,json.dumps(refs),'candidate PC-relative load; control-flow validation required'))
c.execute('UPDATE firmware_identity SET value=?,evidence=? WHERE attribute=?',
          ('Exact manufacturer/part unconfirmed. Earlier Yichip/YC500 attribution is a hypothesis, not an identification.',
           'Verified CPU-visible dump, native peripheral drivers and address map available for comparison; no confirmed silicon part identifier.',
           'mcu_part'))
c.execute('INSERT INTO findings(topic,finding) VALUES (?,?)',('qmk-existing-evidence-versus-unperformed-porting',note))
fid=c.execute('select last_insert_rowid()').fetchone()[0]
c.execute('INSERT OR IGNORE INTO finding_relations VALUES (?,?,?)',(fid,30,'replaces unsupported categorical QMK impossibility with evidence-led porting work'))
c.commit(); assert c.execute('pragma quick_check').fetchone()[0]=='ok'
top=sorted(references.items(),key=lambda item:len(item[1]),reverse=True)[:12]
print(json.dumps(dict(finding=fid,unique_candidate_register_literals=len(references),candidate_call_targets=len(calls),
                     top_literals=[dict(value=hex(v),references=len(r),first_locations=[x['instruction'] for x in r[:4]]) for v,r in top]),indent=2))
