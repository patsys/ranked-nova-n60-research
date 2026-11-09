# Experiment log: attempts, errors, and lessons

This is a chronological synthesis of the work recorded in the source notes, tool outputs, and hardware validation files in this repository. It preserves failed hypotheses as well as successful results. Dates are local task dates. Links point to the corresponding source/evidence folders.

## 1. Host updater and USB protocol (2 November)

- Started with vendor application files, USB captures, and SQLite analysis. The database helped locate host-side functions and command tables, but host-process addresses were kept separate from MCU addresses.
- Parsed the firmware update capture and mapped GETV/START/DATA/COMPLETE framing. The START payload included a small Thumb stub. Early interpretation assumed ciphertext would be written unchanged because the host sent ciphertext unchanged. That was an inference, not a device-side observation.
- Tested simple echo and delay stubs. ACK status `04` only showed protocol acceptance; it did **not** prove a custom stub return reached the host. Early echo/conditional-delay trials therefore failed as proof of two-way communication.
- Improved the method by making bounded timing probes, recovering caller/return context, then reusing the native USB response callback. Repeated changing byte replies and later 56-byte reads established an actual response channel. The lesson: distinguish a protocol ACK from bytes returned by the uploaded code.

Evidence: `research/03-bootloader-stubs/captures/`, `research/03-bootloader-stubs/`, and the legacy notes under `docs/history/`.

## 2. Read-only firmware acquisition and plaintext boundary (2–3 November)

- Built a RAM-only diagnostic path before trying any custom flash programming. It read bounded CPU-visible memory and validated block responses. Two full 128 KiB CPU-view passes matched.
- The CPU view showed readable ARM Thumb code. This was not equivalent to a physical SWD dump: the bootloader transforms data before programming, and user-visible CPU reads can reflect decoded bytes.
- A source-buffer experiment changed the interpretation of the update path. The updater transmitted ciphertext, while a native bootloader operation transformed it before the flash-program path. The measured first four bytes changed from `f0 6d 17 be` to `50 1c 00 20`. The earlier “ciphertext reaches flash unchanged” explanation was rejected.
- Memory reads were bounded, and the diagnostic stub did not include flash erase/program calls. Vendor firmware images and update captures are not published; `evidence/MANIFEST.json` keeps their SHA-256 and `docs/REPRODUCING.md` explains how to produce them from your own keyboard.

Evidence: `research/04-firmware-dump/`, `research/05-ram-bypass/`, and `research/03-bootloader-stubs/`.

## 3. Encryption analysis (3 November)

- The initial algorithm guesses were not sufficient. Offline tests compared candidate direction/layout/header hypotheses against captured blocks.
- The embedded update key and per-file key derivation were later recovered from the captured profile and checked against the full update. The validated transformation uses AES-128 forward/ECB operations in two passes, with per-file keying from the file header. Re-encryption reproduced the captured ciphertext; decoded executable bytes matched the independently acquired CPU image.
- This establishes the captured Nova update profile, not every model/OEM or every board revision. The cryptographic conclusion is specific to the included capture and device.

Evidence and scripts: `research/02-update-crypto/`.

## 4. Boot acceptance, recovery, and bounded flashing (2–3 November)

- Several early QMK images had correct flash readback but failed to enumerate or type after cold start. Readback was not treated as proof of a working application. Warm-RAM tests also failed to establish cold-start behavior.
- Repeated physical Esc-at-reconnect entry exposed differences between the original application, QMK application, and resident bootloader. Some attempts to enter the bootloader from QMK did not work; physical entry remained the reliable path.
- A first QMK physical trial did not enumerate. Stock recovery was completed with a bounded application-only rollback path, and typing was restored. Follow-up startup/vector and USB-controller audits corrected the QMK path.
- A Windows Python environment had a `hid` package collision with the `hidapi` module expected by the flasher. The first invocation failed before opening HID. A dedicated clean flasher virtual environment resolved that tooling error.
- The normal QMK CLI compile and `qmk flash --check-image` route were validated; the flasher uses an application-only range and verifies full readback and protected regions.

Evidence: `research/06-stock-restore/`, `research/07-qmk-port/flash/`, `research/07-qmk-port/validation/`; flasher source: [ry72xx-flasher](https://github.com/patsys/ry72xx-flasher).

## 5. QMK keymap, lighting, Neo2, and NKRO (3–4 November)

- A separate Neo2 userspace keymap was built. The first physical report of missing German-position keys was not a keycode-map error: K/L/Ö sensor values had not settled in the scan-to-key conversion window. Increasing the conversion window from 5 to 20 original timing units restored typing. The user later confirmed the affected keys and ordinary typing worked.
- Initial QMK lighting was off because the RGB path was not enabled/configured in the port. The corrected image enabled the relevant path; the user confirmed the lights returned. Solid red, green, blue, and moving rainbow were exercised. A blue channel looked weaker on Z even with stock firmware, pointing to a physical LED defect rather than a QMK mapping issue.
- The first NKRO candidate stopped producing characters. Endpoint analysis found a missing interrupt-endpoint gate on one reset/submit path. After the endpoint correction, ordinary typing returned and an eight-key chord test passed.
- A remote-wake candidate passed offline checks and a physical key-wake test: a key press woke Windows from sleep, with typing and lighting returning. Lighting also turned off during sleep.
- The maintained upstream-facing keymap uses the conventional ISO layout; Neo2-specific mapping remains a separate append/userspace variant and is excluded from the proposed upstream contribution.

Evidence: `research/07-qmk-port/` and `research/07-qmk-port/validation/`; current sources: [QMK branch](https://github.com/patsys/qmk_firmware/tree/ranked-nova-platform), [QMK userspace](https://github.com/patsys/qmk_userspace).

## 6. Persistent VIA attempts — still failing (3–5 November)

- VIA protocol 13 and dynamic remapping worked in RAM. A test write to unmapped layer 2, row 4, column 9 changed from `0x0001` to `0x0004` and read back immediately.
- The first physical persistence tests disagreed: one user-confirmed cold restart appeared to retain `0x0004`; later queries after a probe/reset returned `0x0001`. This conflict was kept visible rather than reported as success.
- Candidate wear-leveling storage was limited to reserved pages F8–FF and protected by bounds/metadata checks. Driver diagnostics reported a successful flash operation. Comparison with the recovered vendor stub found a page-gate clear mismatch, so the code was changed to clear only the selected bit and reflashed.
- That gate correction did not resolve persistence. A final read-only probe made two full 128 KiB snapshots with identical hashes, left bootloader/metadata/outside-application regions unchanged, and sent no erase/program command. After the probe returned the keyboard to the app, Raw HID GET_KEYCODE returned `0x0001`. The diagnostic-reported CPU word at `0x1F744` remains erased. Three changed bytes are present at `0x1F408..0x1F40C`, but their meaning does not yet explain the runtime result.
- **Current conclusion:** the page-gate change is a tested candidate, not a root-cause fix. Persistent VIA is not verified and the QMK PR gate stays closed. Do not issue more NVM writes until controller address encoding, wear-leveling offsets, and the observed flash bytes are reconciled offline. No reset/format/erase operation was used by this persistence investigation.

Evidence: `research/07-qmk-port/validation/via_persistence_audit.json` and `research/07-qmk-port/results/final-read-only-probe/`.

## 7. Authored loader tests and the soft brick (4 November)

- Two hardware tests of the authored open-source RAM loader with the plaintext START header: erase worked, but every even program word stayed erased while odd words were correct. A 130-cycle delay before the start bit did not help.
- After the second failed write, the read-only recovery holder was stopped in order to attempt a takeover. That was an operator error: the board left the bootloader and was stuck in a half-erased application. SWD recovery with an ESP32 bit-bang probe was attempted; a test pad was damaged and the board was set aside.
- Rule adopted afterwards: never stop the holder after a failed write; restore first.
- Final state (9 November): plugged into a Mac, the board produced no USB device and no USB
  host event within three minutes. Bootloader v1.0.5 starts the application without a
  checksum check while the info-flash patch list is valid, so it jumps into the broken image
  before USB is up; pin entry is disabled and the retained request does not survive power
  loss. With the SWD clock pad torn and chip-level soldering ruled out, the board is retired
  (spare parts). A replacement unit cost about 23 euros.

Evidence: the loader source in [ry72xx-flasher](https://github.com/patsys/ry72xx-flasher) and the 7 November analysis below.

## 8. Second N60, bootloader v1.0.7, flash-controller root cause (7 November)

- The new unit reported GETV `a1070000a1040000` (`ry72xx_boot_usb_v1.0.7`). All tooling refused it. Register-only START timing probes showed identical framing and calibration, but a different native frame: LR `0x1049` instead of `0x1021`, saved return at `[sp,#60]` = `0xce7`, resume `0xe94`. A v1.0.7 read stub was built from these values, cross-checked against the timing reads and used to read flash, info flash and side-effect-free peripheral registers.
- The v1.0.7 boot decision always checks the application XOR from the info-flash metadata; v1.0.5 skips it while the patch list is valid. The flasher now sets the reserved vector word `0x201C` so the check passes.
- Scratch-page diagnostics (page `0xA0`, whole-flash comparison after every run): the first STATUS read after the start bit is `0x1`, busy (`0x3`) follows one read later, and DATA/ADDRESS written while busy redirect the running operation. A replica of the authored loader's `flash_go` reproduced the lost word; polling bits 1:0 fixed it. This explains the 4 November failure.
- Factory data: info flash `0x10000200..0x1000023f` is mirrored into flash-controller registers by hardware; the oscillator trim table selects 48 MHz (live registers matched the prediction).
- The fixed loader flashed QMK on the v1.0.7 unit with full readback verification. The QMK port was cleaned up for upstream (Bootmagic/QK_BOOT, no diagnostics, GPL-2.0-or-later, data-driven keyboard.json) and a newlib syscall conflict with QMK's GCC 15 toolchain was fixed.

Evidence: `docs/BOOTLOADER_V107.md`, `research/08-bootloader-v107/results/`, `research/08-bootloader-v107/`, [QMK branch](https://github.com/patsys/qmk_firmware/tree/ranked-nova-platform).

## Lessons that changed the investigation

1. A success ACK is not proof that a custom return value arrived.
2. A correct flash readback is not proof of cold-start USB operation.
3. A CPU-visible dump is not automatically the same as raw physical flash.
4. A live runtime cache read is not proof of persistence. Require independent cold-start VIA and raw-flash evidence.
5. Keep failed trials and revised conclusions next to the passing result; do not overwrite earlier evidence with the latest story.
6. Isolate Python HID dependencies. A host package collision can fail before any USB operation and must not be mistaken for a device failure.
7. Check the bootloader revision first; an unknown revision means read-only analysis until every native address is verified.
8. Measure peripheral behaviour on a disposable page before trusting an emulator model; the model is only as good as the measurement behind it.
9. Never stop a recovery holder after a failed write.
