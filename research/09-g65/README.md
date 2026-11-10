# 09 · Ranked G65: identification, backup and boot decision

**When:** 9–10 November 2026 · **Status:** QMK with Neo2, VIA and RGB running on the board

A Ranked G65 ("Guardian 65% Keyboard", ISO UK) was connected. Its PCB carries an RY7203 and an
RY1206 v1.0. The identification, backup and analysis below were read-only; QMK was flashed only
afterwards (see "QMK port and flashes").

## Identification

| | G65 | Nova N60 #2 |
|---|---|---|
| Stock application USB | `3532:a0c2`, bcdDevice `0x0002`, serial `RYMicro` | `3532:a0a3`, bcdDevice `0x0004`, serial `rankednova` |
| HID layout | 6 collections: boot keyboard (if 0); keyboard, consumer, mouse, system, vendor `0xff00` 64/64 (if 1) | same |
| Bootloader USB | `352d:1101` "RY USB Adapter" | `352d:1101` |
| GETV | `a1070000` `a1020000` | `a1070000` `a1040000` |
| Boot region `0x0000..0x1fff` | SHA-256 `eae819e4…`, `ry72xx_boot_usb_v1.0.7` | **identical** |

The stock mode switch `04 a5 01` on the vendor collection entered the bootloader, as on the N60
(`g65_getv.py`, `results/getv.json`). Replugging returned to the stock application.

The second GETV word is the board ID. The dispatcher reads it from the info-flash metadata word
`0x1000062c` (`0x10a2`: `ldr r0,[r7,#0x2c]` with `r7 = 0x10000600`) only to build the GETV reply.
The START handler does not compare it with the START header, so the flasher's authored header
(revision field `0xa104`) is accepted on the G65; the read stubs below ran with it.

## Backup

`g65_backup.py` drives ry72xx-flasher's own core and read stubs with the v1.0.7 profile, without
loader, DATA or release. The stubs' guard returns without a reply unless the native return
addresses match v1.0.7, so a different bootloader layout would only have timed out.

- Boot region read first: identical to the N60 v1.0.7 bootloader.
- Two full 128 KiB reads and two metadata reads (`0x10000600..0x100007ff`) matched:
  flash `84d15762…`, metadata `6826af68…` (`results/backup_result.json`).
- The board returned to the stock application after a replug.

## Flash layout from the metadata

| Field | G65 | Nova N60 |
|---|---|---|
| `+0x08` bootloader length / `+0x0c` XOR | `0x1834` / `0xcb9380f2` | same |
| `+0x1c` flag, `+0x20` start | `1`, `0x2000` | same |
| `+0x24` application length | `0x10ebc` (end `0x12ebc`) | `0xe908` (end `0x10908`) |
| `+0x28` application XOR | `0x6ebdc193`, recomputed equal | `0x25a4f084` |
| `+0x2c` board ID | `0xa102` | `0xa104` |
| `+0x100` recovery pin pair | `0xffffffff` (none) | same |
| `+0x114` alternative boot-request magic | `0xffffffff` (default `0x5ac396c5`) | same |
| `+0x150..` patch list | `[0x400130e8]=0xffff0000`, `[0x400130ec]=0xffffffff` | same |

Non-blank pages after the application: `0x1a000..0x1d9ff` (pages `0xd0..0xec`, stock settings).
Pages `0xed..0xff` are blank.

The application is about 9 KiB longer than the N60's. ry72xx-flasher 0.2.0 wrote a fixed
117 pages (`0x2000..0x109ff`) and would have left the end of the G65 application stale on a
restore; the flasher now takes the board from the GETV board ID, requires the backed-up metadata
to agree, and writes the board's application pages (G65: 136 pages, `0x2000..0x12fff`).

## Boot decision: no hardware recovery entry

Disassembly of `0x720..0x860` (identical on both boards):

- `r4 = [0x10000700]`. If it is not `0xffffffff`, bits 5:0 and 13:8 name two GPIO pins, both are
  configured with pad function 5 (`0x484`), and if both read low (`0x4ac`) the bootloader stays.
- `[0x4001400c]` (retained register) equal to `[0x10000714]`, or to `0x5ac396c5` when that word is
  erased, keeps the bootloader and clears the register.
- Otherwise the metadata header XOR, flag and application XOR decide (v1.0.7 always checks).

On the G65 (and the N60) `0x10000700` is `0xffffffff`: **there is no key or pin that forces the
bootloader**. The only entries are the firmware request (`0x5ac396c5`, as used by stock
`04 a5 01` and QMK `QK_BOOT`) and a failing application checksum. `docs/BOOTLOADER_V107.md`
previously named `0x10000714` the boot GPIO; corrected.

Consequence for a QMK port: a first build must offer a bootloader entry that does not depend on
reading keys, for example the `04 a5 01` request on a raw HID endpoint.

## Key scan: 5 banks × 14 channels, 69 keys

The G65 is a 65% board (the Nova N60 is 60%). Its stock acquisition routine `0x5138` (offline,
from the backup) has the same structure as the N60's `0x4cb0` (`research/04-firmware-dump/key_scan_analysis.md`):
enable the ADC (`[0x4000e000] = 1`), per bank write the bank pin mask to `0x40018010`, wait 10,
start (`[0x4000e014] = 1`), wait 5, write the mask to `0x40018020`, read each channel at
`0x4000e09c + 4*channel` (low 16 bits), set the bank bit above 30 and clear it below 20.

| | G65 | Nova N60 |
|---|---|---|
| Banks × channels | 5 × 14 (`0x5202`, `0x51f6`) | 6 × 11 |
| Bank pin codes | `24, 23, 22, 21, 20` (flash `0x11933`) | `24..19` |
| Channel table | `0..13` (flash `0x11925`) | `0..10` |
| Populated positions | 69 | 62 |

The table at flash `0x12764`, indexed `channel*5 + bank`, gives each scan position a logical key
index `row*21 + col`; value `1` marks the unused position (bank 4, channel 6):

```
bank 0  21  22  23  24  25  26  27  28  29  30  31  32  33  34
bank 1  42  43  44  45  46  47  48  49  50  51  52  53  54  75
bank 2  63  64  65  66  67  68  69  70  71  72  73  74  76  77
bank 3  84  85  86  87  88  89  90  91  92  93  94  95  96  97
bank 4 105 106 107 111 114 115   1 116 117 118 119  98  56  35
```

Logical rows 1-5 hold 15, 14, 15, 15 and 10 keys (columns 14 form the right-hand column; row 5
uses columns 0, 1, 2, 6, 9-14): an ISO 65% layout (this unit is ISO UK; the scan is the same
for any ISO legend set, the language only affects the host keymap). A US (ANSI) G65 also exists
and is not examined: it lacks the ISO key and has a different Enter/backslash arrangement, and its
USB PID, board ID, application length and position table are unknown. The flasher refuses an
unknown board ID or PID before writing. The stock default keymap (flash `0x127aa`, 16-bit HID
usages indexed by key id) confirms the positions: right-hand column Del, End, PgUp, PgDn;
bottom row Ctrl, Win, Alt, Space, AltGr, Fn (`0xff`), `0xfe`, Left, Down, Right. The keys are read
by the MCU's own ADC channels, as on the N60; the RY1206 is not in this path.

Remaining scan setup checked against the stock code and identical to the N60 apart from the
channel count: ADC setup `0x3248` (clock bit `0x800`, `e084=1`, `e098=15`, `e080=16`, `e008=14`,
14 channel enables) and GPIO setup `0x45d8` (pins `0x45`/`0x41`, bank pins, analog pins `0x32`).

## Switch measurement: on/off, no travel information

A development build exported the raw samples (`g65_sensor_log.py`, `results/sensor_measurement.json`).
At rest every key reads 0; pressed keys read a steady 135-137, with no values between about 10 and
130 in 1528 samples at ~76/s. The switches therefore behave as on/off contacts read through the ADC,
not as Hall-effect sensors (which would sit near mid-scale at rest and change with travel). The stock
firmware matches this: fixed thresholds (`>30` press, `<20` release) are immediates in `0x5138`, and
the raw values are otherwise only streamed to the host in a vendor report mode (`0x50f8` → `0xf0e0`).
Adjustable actuation and Rapid Trigger are not possible with these switches and were not added.

## LED controller: I2C, 14 × 8 slots, border ring

Unlike the N60 (SPI at `0x40005000`), the G65 drives its LED controller over I2C:

- Peripheral `0x40000000`: `+0x00` enable, `+0x04`/`+0x08` SCL/SDA pin codes `0x62`/`0x63` (pad
  function word `0x341`), `+0x0c` address << 1 | read, `+0x10` divider `(48 MHz / 2 MHz) / 4 - 1 = 5`,
  `+0x18` length, `+0x1c`/`+0x20` RX/TX DMA buffers, `+0x30` status (bit 0 done, `0x16` errors),
  `+0x34` start (3), `+0x40` DMA enable, `+0x44` bit 0 busy, `+0x48` clear (`0x1f`). Init
  `0x4cf8`/`0x4da8` (2 MHz from `0x5f30`, configuration `54 01 62 63` at RAM `0x20000568`, recovered by
  emulating the stock reset path in Unicorn, `g65_emulate_init.py`).
- Controller address `0x34`; DMA write `0x4cb8`, one-byte reply read `0x5ef4`.
- Frame (packer `0x3ca0`, 341 bytes): `[cmd, 14, 8, key level, border level]`, then three planes of
  14 channels × 8 slots. Normal frames use command `0xc0`; `0xc1`/`0xc2` are further commands. The
  two levels come from the lighting profiles at `0x20000030`/`0x20000038` (range 0-4, default 4).
- Slots 1-5 of each channel are the key LEDs (scan bank + 1, fill routine `0x6094`); slots 0, 6 and
  7 hold a 40-LED border ring (table `0x11cc9`): `(0-5, 7)`, `(0-13, 0)`, `(13-8, 7)`, `(13-0, 6)`.
- Start-up handshake `0x3544`: an all-off frame must be answered with `0xa5`; otherwise the stock code
  pulses the reset lines `0x45`/`0x41` (`0x45f8`) with growing delays and retries forever.

The first QMK driver gave up after about a quarter of a second. That only worked right after flashing,
while the controller stayed powered; after a cold power-up the LEDs stayed dark. On a cold start the
controller answered on the 8th attempt, about two seconds after power-up. The driver now keeps retrying
every 300 ms (reset pulse every fourth attempt) without blocking the keyboard. Red, green and blue were
confirmed on keys and border.

## QMK port and flashes

`keyboards/ranked/g65` in the [QMK fork](https://github.com/patsys/qmk_firmware/tree/ranked-nova-platform)
shares the N60's scan code (`keyboards/ranked/common`) with the G65 tables, uses `LAYOUT_65_iso`,
USB `3532:a0c2`, wear-leveling pages F8-FF (erased and permitted on this unit) and the I2C LED driver.
The Neo2, Neo2-with-VIA and VIA keymaps are in [qmk_userspace](https://github.com/patsys/qmk_userspace),
with the VIA definition `keyboards/ranked/g65/ranked_g65_via.json`.

Six images were flashed with ry72xx-flasher, each with full readback and the bootloader, the stock
settings and the metadata unchanged (`results/qmk_flashes.json`). Typing, VIA with saving across a
power cycle, the three colour channels and the border ring were confirmed on the board.

Development builds (`RANKED_DIAGNOSTICS=yes`) add a raw HID bootloader request that needs no key
(`07 00 B0 'RYBL'`, `g65_qmk_bootloader.py`) and read-only LED status (`08 00 B1`, `g65_led_status.py`)
and sensor queries (`08 00 B2 <bank>`). Normal builds contain none of them, so the bootloader is
entered only by key (Bootmagic Esc, `QK_BOOT`), as in upstream QMK.

## Contents

| Path | What it is |
|---|---|
| `g65_getv.py` | Stock mode switch and one GETV; nothing else is sent |
| `g65_backup.py` | Read-only boot, flash and metadata backup through ry72xx-flasher's read stubs |
| `results/getv.json` | Enumeration before/after the switch and the GETV reply |
| `results/backup_result.json` | Hashes, timing and core state of the two backup passes |
| `g65_emulate_init.py` | Runs the stock reset path in Unicorn up to the I2C init and prints its RAM inputs |
| `g65_qmk_bootloader.py` | Raw HID bootloader request (development builds only) |
| `g65_led_status.py` | LED controller status and RGB Matrix settings (development builds) |
| `g65_sensor_log.py` | Raw sample log of all positions over raw HID (development builds) |
| `g65_via_color.py` | Set the RGB Matrix effect, colour and brightness over VIA, without saving |
| `results/qmk_flashes.json` | Hash-only results of the six QMK flashes |
| `results/sensor_measurement.json` | Summary of the switch measurement |

## Not included

The G65 bootloader, stock application, settings pages and metadata are not published;
`evidence/MANIFEST.json` lists their sizes and SHA-256 values with `"included": false`.

## Next

- Restore the stock application from the backup once, to validate the flasher's restore path on
  the G65 (136 pages).
- Media keys (the stock firmware has a consumer collection), LED controller sleep (`0xc1`/`0xc2`),
  reactive lighting.
- A US (ANSI) G65 would need its own USB ID, board ID and position table.
