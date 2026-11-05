# Original keyboard acquisition and GPIO evidence

Analysis is offline against verified `flash_cpu_pass1.bin`, SHA256
`5adca278d90a0672e05dfe5ad47d1635242f9ec0ff78827d83d9f28d6ccd8b49`.
No device access, flash operation, or SQLite change was performed.
`recover_scan_tables.py` reproduces table extraction, including execution of the
original scatter decompressor in Unicorn without any peripheral mapping.

## Concrete result

The original code contains a **6-bank × 11-channel sample acquisition path**,
with **62 populated positions**. This is strong evidence for an analog-style
keyboard scan rather than a conventional digital row-input matrix. The sensor's
physical technology (Hall, capacitive, or other) is **not proved** by this code alone.
The exact MCU/package pin names remain unidentified.

The batch acquisition routine is at `0x4cb0`. It is guarded by byte `0x200002ca`;
`0x4db8` clears that guard. Startup routine `0x4e88` calls clear/acquire/clear and
uses the resulting position list. Do not interpret this one batch routine as a
complete reconstruction of the normal timing/interrupt scheduler.

## Pin and register behavior

| Function/address | Observed behavior |
|---|---|
| `0x4424` | Configure encoded pin `p` with word `(r1<<8) | (r2<<4) | r3`; skip bank index 1. Address is RAM-table base `[0x20000458 + 4*(p>>5 & 3)] + 4*(p&31)`. |
| `0x444c` | Configure encoded pin with `(r1<<8)+1`, same address formula and bank-1 exclusion. |
| `0x44bc` | Write `1<<(p&31)` to `0x40018020 + 4*(p>>5 & 3)`. |
| `0x44d8` | Write the same mask to `0x40018010 + 4*(p>>5 & 3)`. |
| `0xdf0c` | Configure six bank pins through `0x444c`, `r1=0`. |
| `0xde24` | Write each bank-pin mask through `0x44bc`. |
| `0xdeec` | Configure 11 acquisition pins via `0x4424`, arguments `r1=0,r2=3,r3=2` (word `0x32`). |
| `0xdecc` | Restore those pins via `0x4424`, arguments `0,0,2` (word `0x02`). |

The decompressed RAM pin-configuration base table is
`[0x40018090, 0x40018148, 0x4001810c, 0x4001812c]`.
These are recovered values, not guessed vendor register names.
The six bank-pin codes at flash `0xf61a` are **24,23,22,21,20,19**;
all are in encoded bank 0. The 11 acquisition-pin codes at `0xf620` are
**0,1,2,3,4,5,6,7,8,9,10**. Encoded identifiers are not package pin numbers.
Atomic write polarity has not been measured; call the operations `write10` and
`write20` until electrical set/clear meaning is verified.

## Acquisition sequence and storage

At `0x4cbe`, configure acquisition pins (`0xdeec`), then write 1 to
`0x4000e000`. For each bank:

1. Write its mask to `0x40018010` (`0x4cd4..0x4ce8`).
2. Call delay helper `0xdde8` with 10.
3. Write 1 to `0x4000e014` (`0x4cf0..0x4cf2`).
4. Call delay helper with 5.
5. Write the bank mask to `0x40018020` (`0x4cfa..0x4d0e`).
6. Read each enabled channel's result at **`0x4000e09c + 4*channel`**, retaining
   the low 16 bits (`0x4d20..0x4d3c`).

Delay arguments are exact, but their units are not established here. The result
channel table at `0xf60f` is 0 through 10. Results are stored at
**`0x20000b2a + 22*bank + 2*channel`**. A per-channel bank bitset at
`0x20000bae + 2*channel` is set for sample >30, cleared for sample <20, and
unchanged for the intermediate range (`0x4d3e..0x4d68`). This is a concrete
hysteresis rule of this path; do not assume these are final physical actuation
thresholds for every operating mode.

The active-position list begins at `0x20000d5d`; each entry is
`(bank<<4)|channel`, with count at `0x200002d0`. The acquisition block is disabled
by writing 0 to `0x4000e000` before restoring pin configuration (`0x4d7e..0x4d84`).

Initialization `0x31b4` enables all 11 result channels by OR-ing their bit masks
into `0x4000e00c`. It also writes `0x4000e084=1`, `0x4000e098=15`,
`0x4000e080=16`, and `0x4000e008=14`. Peripheral clock/reset and the precise
register specification still need recovery before this becomes a standalone driver.

## Position-to-original-key mapping

Flash `0xf660` is indexed as `[channel*6 + bank]`. Value **1 means absent** in
this scan path, not HID usage 1. Entries are original logical key identifiers,
not directly QMK keycodes. `0xd658` also uses this table to translate packed
positions into original keymap/configuration lookups; `0xcfc8` uses it when
packaging acquisition diagnostics.

| Channel | Bank0 pin24 | Bank1 pin23 | Bank2 pin22 | Bank3 pin21 | Bank4 pin20 | Bank5 pin19 |
|---|---:|---:|---:|---:|---:|---:|
| 0 | 21 | 42 | 63 | 84 | 105 | absent |
| 1 | 22 | 43 | 64 | 85 | 106 | 32 |
| 2 | 23 | 44 | 65 | 86 | 107 | 33 |
| 3 | 24 | 45 | 66 | 87 | 111 | 34 |
| 4 | 25 | 46 | 67 | 88 | 115 | 53 |
| 5 | 26 | 47 | 68 | 89 | 116 | 54 |
| 6 | 27 | 48 | 69 | 90 | 117 | absent |
| 7 | 28 | 49 | 70 | 91 | 118 | 74 |
| 8 | 29 | 50 | 71 | 92 | 95 | 75 |
| 9 | 30 | 51 | 72 | 93 | absent | 76 |
| 10 | 31 | 52 | 73 | 94 | 97 | absent |

This supplies a defensible acquisition geometry for a custom QMK matrix driver.
It does not yet supply a physical ISO layout/keycode map, complete analog clock
and calibration setup, exact MCU pin labels, or verified real-time scan scheduling.
