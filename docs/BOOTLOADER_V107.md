# Bootloader v1.0.7 and flash controller — findings (7 November, second Nova N60)

Tools: `research/08-bootloader-v107/`. Evidence: `research/08-bootloader-v107/results/`.
The v1.0.7 bootloader, stock application, info-flash and RAM dumps referred to below are
not published; `register_snapshot_v107.json` lists them by size and SHA-256.

Unit: stock application `3532:a0a3` release 4, bootloader GETV `a1070000a1040000`,
string `ry72xx_boot_usb_v1.0.7` at 0xC0. No flash or info-flash write was made.

## Method (all read-only)

1. START timing channel (register-only probes, v1.0.5 method): calibration identical
   to v1.0.5 (cal0 2.1 ms, cal8 177.1 ms). `v107_lr_probe.py`, `research/08-bootloader-v107/results/v107_lr_readback_live.json`.
2. One-byte timing reads of code and stack, each nibble accepted only after two agreeing
   sessions: `v107_timing.py`, `v107_timing_live.json`.
3. v1.0.7 read stub from the measured identities (`v107_stubs.py`, emulator tests
   `test_v107_stubs.py`), live cross-check against the timing bytes, then two full dumps:
   two whole-flash passes (SHA-256 b1976a71…, not published) and two info-flash passes (not published).
   All seven timing-read ranges match the dump.

## Native identities for START stubs

| | v1.0.5 | v1.0.7 |
|---|---|---|
| incoming LR (bl 0x22c) | 0x1021 | 0x1049 |
| START handler frame | add sp,#0x24 (0xf60) | add sp,#0x2c (0xf88) |
| saved return | [sp,#52] = 0xcc3 | [sp,#60] = 0xce7 |
| reply builder / callback | 0xbbc, [ctx+0x214] | 0xbe0, [ctx+0x214] |
| resume (memset ctx, loop) | 0xe70 | 0xe94 |
| bootloader SHA-256 (0..0x1fff) | e46c6d93… | eae819e4… |

The v1.0.5 GUARD is inert on v1.0.7 (emulator test and live: wrong LR/frame → no write).
After a redirected read the bootloader is idle in its main loop; getv then answers
instead of resetting. Exit = inert cal0 START, then getv (`v107_read.exit_session`).

## What changed in the code (byte diff)

- New helper at 0x458: copies the 0x18-byte version string at 0xC0 to RAM 0x200002ec
  (via the memcpy at 0x934 = v1.0.5 0x910), called by START.
- START handler: 8 more bytes of locals, one extra call.
- DATA handler 0x1032–0x1096 extended (+0x20).
- **Boot decision (0x7a0–0x860) reordered.** Literal pool otherwise identical.

### Boot decision, the important change

v1.0.5: retained request 0x5ac396c5 → bootloader. Otherwise, if the info-flash patch
list (0x10000750, (address, value) pairs restricted to 0x400130d0..0x400130ec) is
present and valid, **jump to the application without the GPIO and checksum checks**.

v1.0.7: retained request → bootloader. Then **always**: boot GPIO (0x10000714),
metadata header XOR, application XOR; only afterwards the patch list is validated.
Any failure → 0xffff0002 → stays in the bootloader (recoverable, not a brick).

Checksum (0x40c) = XOR of 32-bit words. Metadata (0x10000600):
- +0x08 bootloader length 0x1834, +0x0c XOR 0xcb9380f2 (verified)
- +0x1c flag 1, +0x20 start 0x2000, +0x24 length 0xe908, +0x28 XOR 0x25a4f084 (verified
  over the stock application)
- 0x100007fc = XOR over 0x10000600..0x100007fb = 0x9df9d9e5 (verified)

Patch list on this unit: [0x400130e8] = 0xffff0000, [0x400130ec] = 0xffffffff
(write gates for pages 0xd0–0xff), identical to the v1.0.5 unit.

## Consequence for QMK on v1.0.7

A QMK image is booted only if XOR(0x2000 .. 0x2000+len) equals the stored value. The
current authored flow (no metadata write, relying on the patch-list bypass) would leave a
v1.0.7 board in the bootloader after flashing QMK — recoverable, but QMK would not run.
Options: (a) compensation word so the XOR over the fixed checked range 0x2000..0x10908
(QMK followed by erased FF) equals 0x25a4f084. The image size does not matter: bytes after
0x10908 are not checked. The word can sit anywhere inside the range; the reserved
Cortex-M0 vector entries 0x201C..0x2028 are never used by the core (QMK has 0x2173 there);
(b) update the metadata application entry and header XOR like the vendor tool does.
Neither has been tried. The application itself is byte-identical to the v1.0.5 unit's.

## Read-only hardware snapshot for the emulator (`register_snapshot_v107.json`)

Read in the bootloader (inside a START redirect), one session per window, all word loads
from `v107_stubs.WORD_WINDOWS`; the application returned after every session.

- SCB: CPUID 0x410cc200 (Cortex-M0 r0p0), ICSR 0x00400000, AIRCR 0xfa050000, CCR 0x208,
  all fault/priority registers 0. VTOR reads 0 (not implemented on M0).
- NVIC: ISER 0 (the bootloader polls, no IRQ enabled), ISPR 0x10 (IRQ 4 pending), IPR all 0.
- SysTick: RVR 0xffffff, CVR 0xffffff, CALIB 0x80000000 (NOREF, no TENMS) — unused.
- ROM table 0xE00FF000 reads all zero (entries, PIDR, CIDR): no CoreSight ROM table, so
  designer/part cannot be identified this way. Reads did not fault.
- Flash controller timing registers equal the authored loader's init values at 48 MHz:
  +14 0x207, +18 0x0b, +20 0x40, +24 0x137, +28 0x144, +30 0x104, +38 0x114,
  +3c 0x34bc0, +40 0x15f900, +4c 6. **+80 = 0xbb80 = 48000 (core clock in kHz).**
  Further non-zero registers (meaning unknown, kept as reset/boot values):
  +60/+64/+6c/+70 0xffffffff, +74 0x00081004, +78 0x26, +7c 0x0f00003c,
  +84 0x01e50000, +88 0x03d80020, +8c 0x01d50030, +90 0x02c50040, +94 0x02b30060,
  +98 0x00010400, +9c 0x78, +a0..+ac 0xffffffff. COMMAND/ADDRESS/DATA/STATUS read 0.
- System control 0x40014000: +04 4, +10 0x35, +1c 0x21, +28/+2c/+30 0x800c0c20,
  +34 1, +38 4, +44 0x20, +4c 2, +50 0x0100b1b1 (= info flash 0x1000071c), +54 0x110,
  +5c 1, +60 2, +64 1, +108/+110/+114 0xf, +120 0x3f, +130 1, +134 0x00ddc99d.
  Retained request word +0x0c reads 0 inside the session.
- RAM 0x20000000..0x20001c50 twice (`ram_a.bin`, `ram_b.bin`): 12 words differ, all
  0x20000244 (counter) and 0x20001bd0..0x20001bf8 (stack residue below the application SP).
  Native context at 0x20000324 holds our reply header; guard words at 0x20000754 are
  0x5a5a5a5a, 0xa5a5a5a5, 0 (programming not armed).

Not read on purpose (read side effects possible): USB 0x40017xxx, crypto 0x4000d000,
unknown blocks 0x40012100, 0x40015000, 0x40016000, 0x40018000, 0x40019000, SysTick CSR.

## What the register values mean (static xref `xref_registers.py` + live reads)

### Factory block in the info flash, mirrored by hardware

Info flash 0x10000200..0x1000023f is mirrored word for word into flash controller
+0x60..+0x9c (no code writes those registers; values identical, including the FF words).
So that block is factory data loaded by hardware at reset. Further factory words:
0x100003f0 = 0x7e934457, 0x100003fc = 0x7204eb81 (unknown; possibly ID/check).

### Oscillator calibration table (0x10000224 + 4*mode), used by clock setup 0xa60

The bootloader (0xa60) and the stock app (0xea60) contain the same clock setup:
`clock_setup(mode 0..4, divider <= 15)`, oscillator controller **0x40019000**:
- +0x0c bits 10:8 = entry bits 6:4 (frequency select)
- +0x10 = entry bits 23:16 | (entry bits 27:24) << 16 (fine and coarse trim)
- SystemCoreClock (RAM 0x200002dc) = 24 MHz + select * 4 MHz

| mode | entry | select | frequency | fine | coarse |
|---|---|---|---|---|---|
| 0 | 0x01e50000 | 0 | 24 MHz | 0xe5 | 1 |
| 1 | 0x03d80020 | 2 | 32 MHz | 0xd8 | 3 |
| 2 | 0x01d50030 | 3 | 36 MHz | 0xd5 | 1 |
| 3 | 0x02c50040 | 4 | 40 MHz | 0xc5 | 2 |
| 4 | 0x02b30060 | 6 | 48 MHz | 0xb3 | 2 |

Live 0x40019000: +00 3, +08 4, **+0c 0x02c30600 (select 6), +10 0x000200b3 (mode 4 trim)**,
+14 0xbb80, +38 1, +3c 0x64. The chip runs at 48 MHz from the trimmed RC oscillator; the
prediction from the table matches the live registers exactly. 0xbb80 = 48000 (kHz) appears
in the factory block (0x10000220 → flash controller +0x80) and in 0x40019000+0x14.

### System control 0x40014000

- +0x0c retained boot request (0x5ac396c5, app 0x3edc).
- +0x50 clock/bus configuration with an update bit 24. The bootloader writes 0x0100b1b1
  (same value as info 0x1000071c) and reads it back; the app edits fields [4:0], [7:5],
  [12:8], [15:13] (0x11 / 2 / 0x11 / 2 in its low-power path at 0xd5f0, versus
  0x11 / 5 / 0x11 / 5 from the bootloader).
- +0x4c clock source select, written after setting +0x50 bit 24 (bootloader 0x1228 writes 2,
  then polls **+0x120 bit 0** = ready; +0x120 reads 0x3f live = ready flags).
- +0x60 bit 1 set by both; +0x28 cleared by the app; +0x18 written by the bootloader
  helper 0xaf0; +0x124/+0x128 used by the app (0x3f written to +0x124).

### Flash controller 0x40013000

Only the stock application programs it (init 0x37a0, erase 0x38d0, program 0x3970 /
0x3a2c, start/wait 0x3f98); the bootloader only writes the gate registers from the info
flash patch list. Timing registers scaled by MHz/48 are real times at 48 MHz:
+28 0x144 = 6.75 us (word program), +3c 0x34bc0 = 4.5 ms (page erase),
+40 0x15f900 = 30 ms (probably mass erase). Unscaled ones (+14, +18, +20, +24, +30, +38,
+4c) are fixed counts.

## Remaining blocks: code analysis + live snapshot (`register_snapshot_v107.json`)

Helpers: 0x9c4(mask, on) = peripheral clock enable (0x40014000 +0x2c set / +0x30 clear);
0x9e0 = delay in us; 0x238 = NVIC ICER. Live reads were limited to registers that the code
reads without side effects (status bits are cleared only by explicit writes).

- **0x4000D000 AES/DMA engine** (clock bit 10, IRQ 7). Init 0x330: +0x18 = RAM buffer
  0x200007c0 (key/in/out in 16-byte slots), +0x04 = 1, +0x10 or +0x14 = 3 (mode with or
  without key), NVIC IRQ 7. Block op 0x29c: +0x00 = 1 start, poll +0x08/+0x0c (done/error),
  then cleared by writing 0. Live: only +0x18 = 0x7c0 (address register keeps the low
  12 bits = RAM offset); idle.
- **0x40012000 timer with compare** (stock app only): ISR 0x2f20 checks flags +0x14/+0x18/
  +0x20 against enables in +0x30 and clears them by writing 1; +0x40 counter, +0x50 compare
  (0xdc54: compare = counter + delta); +0x34/+0x38 bit 16 start/stop. Live: all zero
  (unused in the bootloader).
- **0x40012100**: not referenced at all (the earlier literal hit was code), not read.
- **0x40015000 timer/power block** (clock bit 19): bootloader 0x5f0 on = +0x00 = 1 then
  wait +0x38 != 0; off = +0x04 = 1, wait +0x38 == 0. App 0x49f0: +0x2c = clk/4 MHz - 1,
  +0x24 period, +0x08/+0x0c = 1; ISR 0x2a44 reads +0x30/+0x34 and clears them with 1.
  Live: +0x20 1, +0x28 0x2db, **+0x2c 0x0b (= 48 MHz / 4 MHz - 1, written only by the
  app)**, +0x38 1 (running).
- **0x40016000 USB core**: 0x1250: +0x00 |= 0x80, 1 us, = 0 (core reset), then endpoint
  setup for EP 0x04 and 0x84; +0x0c = 3 interrupt enable; +0x08 interrupt status (read,
  then cleared with 0). Live: +00 1, +08 1, +0c 3, +10 3.
- **0x40017C00..0x40017FFF USB endpoint area**: EP0 buffer at 0x40017c00 with **one byte
  per 32-bit word** (0x98a writes byte i to +4*i, then the count to 0x40017e80+0x54 to send);
  0x40017e00 buffer offset table (0x20, 0x40, ... set in 0x530); 0x40017e80 +0x50 EP0
  handshake (0x11 stall, 2 ack), +0x54 IN byte count; **setup packet registers at
  0x40017fa0..0x40017fbc (one field per word)**. Live: last SETUP = 80 06 00 03 00 00 ff
  (GET_DESCRIPTOR string 0, from macOS); EP0 buffer still holds string 0 (0x0409) and the
  descriptor tail: vendor HID report 64 in / 64 out, EP 0x84 IN and EP 0x04 OUT interrupt,
  64 bytes, interval 1.
- **0x40018000 GPIO**: +0x30 + 4*port = input data (0x4ac); pad configuration through the
  RAM table 0x20000304 = {0x40018090, 0x40018148, 0x4001810c, 0x4001812c} (port 0..3),
  value (function << 4) | 0x802 per pin (0x484). Live inputs: port0 0x03ffffff, port1 1,
  port2 0x6b, port3 0x7f; pad registers read 0 in the bootloader (no boot GPIO configured).

Observation for the emulator: registers the bootloader never writes still hold the stock
application's values (flash timing, 0x40015000+0x2c), so after the SYSRESETREQ boot entry
these peripherals were evidently not reset (or their reset values happen to coincide).

## Scratch-page flash experiments and the loader bug (2026-11-07)

`run_diag_v107.py` (same safety sequence as run_diag.py, v1.0.7 native path), page 0xA0.
Every run: backup → checks → experiments → final erase → whole flash and info flash
identical to the backup → application back.

Plan matrix (`flashdiag_v107_20261107T155243`): all 9 OK. Erase 24355 busy polls,
program 240 polls per word (~9 cycles per poll at 48 MHz → ~44 us per word, ~4.5 ms per
erase, ratio 101). Single, back-to-back, ADDRESS-rewrite, delay and odd-start variants all
program correctly. **STATUS read immediately after setting the start bit = 0x1.**
ADDRESS reads back the last address; the gate word reads 0 after closing.

Race matrix (`flashdiag_v107_20261107T155719`), IMMEDIATE = authored flash_go timing
(start, one instruction, first poll):
- poll bit 1 only, two words: first poll already "done", word 0 left erased, word 1
  programmed (op1 waited 219 polls for op0's remaining busy time); STATUS during busy 0x3.
- poll bits 1:0, two words: both correct (241 polls each).
- poll bit 1 only, single word: read back during busy = 0x00000000, STATUS 0x3.

Controller model (now in test_diag_stub.py and tests/test_authored_loader.py): start →
first read 0x1 → 0x3 while busy → 0x0; a start while busy is ignored; the running
operation completes with the ADDRESS/DATA present at its end; flash reads 0 while busy.
The model reproduces every hardware result above.

Root cause of the authored-loader failure ("every other program word left erased",
the 2026-11-04 brick): flash_go polled bit 1 one instruction after the start, saw 0x1,
returned, and the next word's DATA/ADDRESS redirected the running operation. Fix: poll
until STATUS bits 1:0 are both clear. Loader rebuilt (SHA-256 22487f07…), regression
tests on the measured model fail on the old image and pass on the new one. The QMK
driver's wait_ready() received the same change (it worked only through call overhead).
Not yet validated on hardware: the full authored loader (it only admits application
pages, and v1.0.7 needs its own flasher profile and the QMK checksum word first).
