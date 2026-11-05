"""Prepare readable disassembly and persist verified CPU flash evidence."""
from pathlib import Path
import json,sys,struct,hashlib,re,sqlite3
sys.path.insert(0,str(Path(__file__).resolve().parent/'.tools'))
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS

out=Path('firmware_dump'); manifest=json.loads((out/'manifest.json').read_text())
assert manifest['verified'] and manifest['passes_identical']
full=(out/'flash_cpu_pass1.bin').read_bytes()
assert full==(out/'flash_cpu_pass2.bin').read_bytes() and len(full)==0x20000
app=(out/'application_plaintext_0x2000.bin').read_bytes()
boot=(out/'bootloader_0x0000.bin').read_bytes()
assert app==full[0x2000:0x1ec00] and boot==full[:0x2000]
md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS); md.skipdata=True

def listing(data,base,path):
    with path.open('w',encoding='utf-8') as stream:
        stream.write('; CPU-visible bytes. Linear Thumb disassembly includes vectors, literal pools and data.\n')
        stream.write('; This is not recovered C source or a complete control-flow/function analysis.\n')
        for i in md.disasm(data,base):
            stream.write(f'{i.address:08x}  {i.bytes.hex():10} {i.mnemonic:9} {i.op_str}\n')

listing(boot,0,out/'bootloader_thumb_linear.txt')
listing(app,0x2000,out/'application_thumb_linear.txt')
reset=struct.unpack_from('<I',app,4)[0]&~1
assert full[reset:reset+4]==bytes.fromhex('07480047')
# Reset's LDR r0,[pc,#0x1c] / BX r0 follows the literal at 0x2230.
startup=struct.unpack_from('<I',full,0x2230)[0]
assert startup&1 and 0x2000<startup<0x20000
listing(full[startup&~1:(startup&~1)+128],startup&~1,out/'startup_thumb.txt')
vectors=[dict(index=i,value=f'0x{value:08x}') for i,value in enumerate(struct.unpack_from('<48I',app))]
summary=dict(full_flash_size=len(full),full_flash_sha256=hashlib.sha256(full).hexdigest(),
             application_region_base='0x00002000',application_region_size=len(app),
             application_sha256=hashlib.sha256(app).hexdigest(),bootloader_size=len(boot),
             bootloader_sha256=hashlib.sha256(boot).hexdigest(),
             stack_pointer='0x20001c50',reset_vector='0x00002211',startup_entry=f'0x{startup:08x}',
             double_read_identical=True,final_state=manifest['cleanup']['final_state'],
             erased_runs=[dict(start=hex(m.start()),end=hex(m.end()),length=m.end()-m.start()) for m in re.finditer(b'\xff{256,}',full)],
             zero_runs=[dict(start=hex(m.start()),end=hex(m.end()),length=m.end()-m.start()) for m in re.finditer(b'\x00{256,}',full)])
(out/'analysis.json').write_text(json.dumps(summary,indent=2)); (out/'vectors.json').write_text(json.dumps(vectors,indent=2))

note=f'''# Verified firmware read — 2026-11-02

The CPU-visible 128 KiB range 0x00000000–0x0001ffff was read twice through
our guarded own RAM stub and native USB transmit callback. Both reads matched
byte-for-byte. This is a live memory dump, not an offline guess at the cipher.

- Full CPU flash snapshot: `flash_cpu_pass1.bin` (131,072 bytes).
- Independent verification pass: `flash_cpu_pass2.bin`.
- Bootloader region: `bootloader_0x0000.bin` (8,192 bytes, base 0).
- Application region: `application_plaintext_0x2000.bin` ({len(app):,} bytes,
  base 0x2000, sliced to the captured image extent 0x1cc00).
- Initial stack pointer: 0x20001c50; reset vector: 0x00002211.
- The reset stub branches through a literal to {hex(startup)} in Thumb mode.

Full SHA256: `{summary['full_flash_sha256']}`.
Application SHA256: `{summary['application_sha256']}`.
Bootloader SHA256: `{summary['bootloader_sha256']}`.

`application_thumb_linear.txt` and `bootloader_thumb_linear.txt` provide raw
linear ARM Thumb disassembly. They include vector tables, literal pools and
data interpreted by the disassembler; they are not recovered C source or a
complete function reconstruction. `startup_thumb.txt` is a focused listing
at the reset-selected startup entry. Import the binaries as little-endian
ARM/Thumb with the load bases above for further analysis.

The application extent is inferred from the captured image size. Its code and
vector base are verified; an exact byte-for-byte mapping of every vendor data
partition into flash has not been independently reconstructed. The full flash
snapshot remains the authoritative read of the selected CPU address range.
This does not establish whether physical flash cells or SWD reads expose the
same representation, identify the cipher/key, or identify the exact MCU part.

The reader returns up to 56 data bytes per START using the native transmit
callback at context+0x214. The own payload modifies a guarded RAM-stack return
word and writes the native RAM reply buffer; it has no flash controller,
erase/program or peripheral access. No firmware DATA or COMPLETE packet was
sent during these dumps. A callback-body mock is used only in offline bounded-
write emulation; physical USB replies and the two matching passes validate
the live output independently.

The normal START/getv cleanup returned the device to six application HID
collections and zero bootloader interfaces. Application USB enumeration is
verified; a complete keyboard functional or separate flash-integrity test was
not performed. Raw request/reply evidence is in `usb_transactions.json` and
the two-pass metadata is in `manifest.json`.
'''
(out/'README.md').write_text(note)

c=sqlite3.connect('ranked_re.db')
c.execute('CREATE TABLE IF NOT EXISTS firmware_dumps (name TEXT PRIMARY KEY, base_address INTEGER NOT NULL, byte_length INTEGER NOT NULL, sha256 TEXT NOT NULL, file_path TEXT NOT NULL, verification TEXT NOT NULL, content BLOB NOT NULL)')
verification=json.dumps(dict(double_read_identical=True,full_flash_sha256=summary['full_flash_sha256'],source='firmware_dump/manifest.json'))
for name,base,file in [('cpu_flash_128k',0,'flash_cpu_pass1.bin'),('bootloader',0,'bootloader_0x0000.bin'),('application_region',0x2000,'application_plaintext_0x2000.bin')]:
    blob=(out/file).read_bytes()
    c.execute('INSERT OR REPLACE INTO firmware_dumps VALUES (?,?,?,?,?,?,?)',(name,base,len(blob),hashlib.sha256(blob).hexdigest(),str((out/file).resolve()),verification,blob))
for file in ['usb_block_reader_live.json','firmware_dump/manifest.json','firmware_dump/usb_transactions.json']:
    c.execute('INSERT INTO diagnostic_experiments(source_file,evidence_json) VALUES (?,?)',(file,Path(file).read_text()))
c.execute('INSERT INTO findings(topic,finding) VALUES (?,?)',('custom-stub-multi-byte-usb-read','Verified native USB transmit callback is stored at packet context+0x214, per complete observed reply builder. Own guarded START entry redirects enclosing handler return into own RAM tail after native register restoration, copies up to56 CPU-read bytes into context+8, sets u16 length at context+4, calls the existing callback and continues at0xe70. Offline exact-flow emulation bounds writes to RAM stack and reply buffer. Live6-byte read0x101c matched independent timing read and56-byte read0x2000 exposed coherent vectors. No DATA/COMPLETE or flash controller operations. Evidence usb_block_reader_live.json.'))
c.execute('INSERT INTO findings(topic,finding) VALUES (?,?)',('verified-cpu-firmware-flash-dump',note))
last=c.execute('select last_insert_rowid()').fetchone()[0]
c.executemany('INSERT OR IGNORE INTO finding_relations VALUES (?,?,?)',[(last,20,'supersedes practical plaintext-inaccessibility claim for this device'),(last,25,'corrects ciphertext-to-flash/XIP-only inference'),(last,29,'supersedes software investigation exhausted claim')])
c.commit()
assert c.execute('pragma quick_check').fetchone()[0]=='ok'
print(json.dumps(dict(summary=summary,last_finding=last,sqlite_firmware_dumps=c.execute('select name,base_address,byte_length,sha256 from firmware_dumps').fetchall()),indent=2))
