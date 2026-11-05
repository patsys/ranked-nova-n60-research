# Neo2 core installed — 3 November 2026

**Latest:** the subsequent missing-key regression is corrected and the user
confirmed operation. See [the timing fix](TIMING_FIX_20261103.md) for the current
installed image, physical before/after results and final verification. The
image hashes and pending-diagnostic notes below describe earlier stages.

**Subsequent physical regression:** the user reports many nonworking keys,
including German K/L/Ö. This image is not functionally validated for general
typing. The complete live VIA map remains correct. Temporary volatile F23/F24
assignments for L/Ö yielded no selected Windows events during the user test;
the Neo2 assignments were restored and verified. The analog cause is not yet
established. A RAM-only raw sensor capture is prepared; no corrective flash
has occurred. See `live_L_Odia_diagnostic.json` and the SQLite findings.

The separate `neo2` keymap was flashed after an Esc-held physical reconnect
entered the original bootloader. Windows must keep German QWERTZ selected.
QMK core and the working hardware drivers were not changed for this keymap.
Standard Key Overrides provide Shift punctuation; a keymap-local
`process_record_user` hook keeps Mod3/Mod4 active while either physical source
remains held.

## Verification

- Final VIA ELF SHA256: `76368aa97ef72d61ebac6afa265fa1fc2725ae0093813d007a87e58f4684559b`.
- Application body SHA256: `dc80c8576d6632775c932a035e5851e48b62dfddd84c290ec0c6c82439aaa64d`.
- All 117 pages at `0x2000..0x10a00` were acknowledged.
- Full 128 KiB readback matched the expected overlay exactly.
- Bootloader, all flash outside the application region, and hidden metadata
  matched the prewrite backup exactly. No COMPLETE command was sent.
- QMK keyboard and VIA raw HID interfaces enumerated; bootloader was absent.
- Read-only VIA checks confirmed protocol 13, three QMK layers and all 396
  keymap bytes matching the compiled Neo2 default. A 15-second query soak passed.
- Offline coverage includes 113 keyboard cases, 219 VIA cases and 29 flash-host
  cases, plus startup, emergency-entry, diagnostic and transport validation.

The physical flash log and complete pre/post backups are in
`qmk_flash/live_qmk_20261103T143629_868253Z/`. Live keymap verification is in
`qmk_port/neo2/live_keymap_validation.json`.

## User verification still needed

Physical typing and Windows character rendering have not been independently
observed. On the physical QWERTZ `Q W E R T Z` positions, expect `x v l c w k`.
Caps/# select Mod3 symbols; ISO<>/right Alt select Mod4 navigation.
Neo levels 1/2 share the base QMK layer via Shift, so four Neo levels occupy
three QMK layers. Unsupported typography is disabled; Greek/math levels 5/6
are absent. Circumflex/grave remain German dead keys. VIA edits are volatile.

The previous working QMK image and its native protocol proof are preserved in
`qmk_port/neo2/working_firmware_before_neo2/`. It was not necessary to roll back.
This is a research port; no official upstream acceptance or publication is claimed.
