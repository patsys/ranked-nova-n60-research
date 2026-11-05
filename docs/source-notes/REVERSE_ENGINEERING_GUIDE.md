> **Historical source note:** this guide predates the 5 November persistence audit. Its positive QMK/keymap observations remain useful, but any statement that VIA persistence passed is superseded by [the current status](../STATUS.md) and [experiment log](../EXPERIMENT_LOG.md).

# Ranked Nova: reverse engineering through working QMK/VIA

Updated 2026-11-03. This is the current reading guide and reconstruction of
the work saved in this workspace. It links the original evidence, scripts,
failed experiments and final result. It is not a verbatim transcript or a
claim that every hardware transaction was continuously captured.

Latest Neo2 result: the separate keymap is installed. A reported missing-key
regression was traced with live raw/debounced sensor queries and corrected by
extending the conversion window from 5 to 20 original helper units. Physical
before/after captures and the user's typing confirmation support the fix;
QMK core is unchanged. See [the timing-fix evidence](qmk_port/neo2/TIMING_FIX_20261103.md)
for current hashes, flash verification and remaining validation limits.

Later cryptographic result: the embedded master key, per-file key and two-pass
AES-forward transform were recovered and verified against the complete captured
update plus an independent physical result. See
[key extraction and verification](crypto_research/README.md).

The user has now confirmed that the installed keyboard works. Tool tests
independently established QMK/VIA enumeration, two-way VIA communication and
reversible remapping. That confirmation does not identify which individual
keys, cold-power cases or suspend/resume scenarios were tested.

## Read this first

| Purpose | Documentation |
|---|---|
| Current installed image and physical results | [Successful result](qmk_flash/SUCCESS_20261103.md) |
| Original host software, encrypted files and capture analysis | [Original report](REPORT.md), historical conclusions explicitly superseded |
| How custom execution and USB readback were established | [Execution proof](readonly_stub/EXECUTION_TEST.md), [USB read channel](readonly_stub/USB_READ_CHANNEL.md) |
| Full plaintext CPU-view dump and limits | [Dump verification](firmware_dump/README.md), [coverage](firmware_dump/COVERAGE.md) |
| Bootloader, encryption path and plaintext bypass | [Crypto path](firmware_dump/BOOT_CRYPTO_AND_QMK.md), [RAM bypass](ram_bypass_test/README.md) |
| Matrix, clock and USB reconstruction | [Matrix analysis](firmware_dump/key_scan_analysis.md), [clock calibration](qmk_port/platform/CLOCK_CALIBRATION.md), [USB analysis](firmware_dump/usb_driver_analysis.md) |
| QMK implementation and build | [Port](qmk_port/README.md), [platform integration](qmk_port/platform/PLATFORM_INTEGRATION.md) |
| Failed flashes, recovery and corrected startup | [Recovery record](qmk_flash/RECOVERY_RESULT_20261103.md), [cold-start audit](qmk_flash/ram_scan/cold_start_audit.md) |
| Bounded physical debugging | [Diagnostic plan](qmk_flash/DIAGNOSTIC_PLAN.md), [runtime diagnostics](qmk_port/runtime/USB_DIAGNOSTIC.md) |
| Stock writer and rollback mechanism | [Bounded stubs](stock_restore/BOUNDED_STUBS.md), [rollback review](stock_restore/ROLLBACK_FROM_BOOT_REVIEW.md) |

## 1. Start from observed host behavior

We inspected the vendor updater/software evidence and the existing SQLite
database before making assumptions about the microcontroller. The database's
host executable functions, call graph, decompiled routines, strings and USB
command records are distinct from the later device-firmware disassembly.
An address in the Windows DLL is not an MCU address.

The updater's read/checksum/send path was compared with `fw_update.pcap`.
`analyze_upload_capture.py`, `extract_vendor_stub.py` and
`analyze_firmware_dump.py` preserve the analysis code. The capture established
that encrypted update payload bytes were sent unchanged by the host. This
alone did not establish what the device subsequently programmed.

The observed identities were stock application `3532:a0a3` (six HID
collections, serial `rankednova`) and native bootloader `352d:1101` (vendor
HID). Application command `04 a5 01` requested the bootloader. The captured
update protocol contained GETV, START, sequential DATA and COMPLETE phases.

The reconstructed START frame was496 bytes: the plaintext440-byte vendor
stub occupied offsets52 through491; its length field was at48 and its XOR
word at492. `vendor_stub.bin` has SHA256
`fbf8d711262615c1fcfa7abad885e124032be8990da9af01f6e31a20da762ae8`.
Stub disassembly exposed Thumb code and flash-controller accesses at
`0x40013000`, including explicit erase/program operations. This motivated
separate diagnostic stubs that did not contain those operations.

See [capture analysis](ANALYSIS_UPDATE.md) and [initial communication tests](COMMUNICATION.md).

## 2. Prove custom execution before trusting acknowledgements

Native ACK status04 was not evidence that a replacement stub's return value
or data reached the host. Early synthetic echo/conditional-delay experiments
did not establish a custom return channel. Those failures were retained.

Register-only finite delay payloads then produced repeatable additional
START/DATA latency. Delay calibration and guarded timing probes exposed small
code/register values while avoiding erase/program routines. Reading LR and
saved return words identified the native call chain rather than guessing it.

Important recovered points were the START initialization entry at uploaded
offset`0x13a`, programming entry`0x6c`, incoming LR`0x1021`, and saved native
return`0x0cc3`. The native exit restored a known stack frame. Generated stubs
checked those identities before changing a single RAM return word. Emulator
negative cases checked that wrong callers caused no such change.

Evidence and builders are in `readonly_stub/`, `test_execution_live.py`,
`read_lr_live.py`, `read_saved_lr_live.py`, `timing_channel.py` and their
adjacent live JSON files. The detailed [caller investigation](readonly_stub/CALLER_TRACE.md)
and [source-buffer investigation](readonly_stub/BUFFER_TRACE.md) describe the transition.

## 3. Recover a real USB response path

Timing-based code reads led to native reply-builder/callback recovery.
Guarded RAM code reused the original USB sender instead of assuming R0 became
an ACK payload. A fixed42 reply and changing43/42/43 replies established that
newly uploaded code could return actual bytes in repeated requests.

Returned bytes at`0x101c` independently matched timing-derived code and
decoded to the expected native call/branch. The one-byte reader was then
extended to a maximum56-byte block reader using the native transmit callback
at context+`0x214`. Only the validated RAM stack word and output buffer were
modified by the diagnostic payload; USB transmission used the native driver.

Relevant tools: `usb_read_channel.py`, `usb_block_reader.py`,
`test_usb_number_live.py`, `test_usb_repeated_live.py` and
`readonly_stub/USB_READ_CHANNEL.md`. This was RAM code loaded through the
bootloader, not a permanently installed read service.

## 4. Establish the plaintext boundary and acquire firmware

The vendor programming entry's source pointer was probed with synthetic
chunks, then the first original captured block. Captured ciphertext beginning
`f0 6d 17 be` yielded source bytes`50 1c 00 20`, consistent with the original
application stack vector. Thus unchanged host ciphertext did not imply
unchanged flash-programmer input. Bootloader-side transformation was supported
by direct observation, not merely encrypted-file statistics.

`dump_firmware_live.py` used the block reader for two full CPU-visible reads
of`0x00000000..0x0001ffff`. Both128KiB passes matched SHA256
`5adca278d90a0672e05dfe5ad47d1635242f9ec0ff78827d83d9f28d6ccd8b49`.
The boot region is`0..0x1fff`; application vectors start at`0x2000`.
The dump, extracted regions, vector/startup analysis and linear Thumb
disassembly are in `firmware_dump/` and the `firmware_dumps` SQLite table.

This is a CPU-visible plaintext snapshot, not proof of complete physical
flash/SWD/OTP coverage or recovery of original C source. CPUID`0x410cc200`
later identified Cortex-M0 r0p0; the exact vendor/part remains unconfirmed.

Boot code showed hardware-assisted16-byte processing through`0x029c` and
peripheral`0x4000d000`. At that stage the key and cipher were unidentified.
Later extraction located the master at boot flash`0x173c`/RAM`0x2000021c`;
testing both header halves and operation directions identified AES-forward
metadata/file-key recovery and two forward AES passes for DATA. Executable
bytes, both checksums, the full inverse ciphertext and an independent512-byte
physical sample validate the result. No new live zero-input experiment was
needed. Absence of software cipher constants had incorrectly been used to
exclude a standard hardware cipher in the initial report.

RAM-only comparison then established that clearing`0x20000214` after START
delivered all512 plaintext DATA bytes unchanged to the diagnostic programmer.
The crypto-enabled control transformed that input. This supported a deliberate
plaintext transfer path without requiring an extracted encryption key.

## 5. Audit boot acceptance, recovery and write boundaries

We read the native-used512-byte metadata region at`0x10000600` separately.
The captured patch list configures`0x400130e8/ec` and bypasses the optional
GPIO and checksum fallback paths. Its GPIO selector is disabled. It was
incorrect to assume an invalid application would always select boot USB.

Software boot entry uses retained request`0x5ac396c5` at`0x4001400c` followed
by ARM SYSRESETREQ. No additional proven native double-tap or physical key
entry was found. Stock Fn1+B+L belongs to stock application code, not an
independent resident recovery handler. QMK therefore implemented its own
early held-key request. Actual Esc-held recoveries and later diagnostic
automatic recovery are recorded; no hardware pad-short procedure was invented.

The native vendor programmer could reach boot pages in some modes; there was
no basis for calling the boot region physically write-protected. The bounded
v3 replacement therefore checks context, source, length and application page
range in RAM code, and disables special metadata operations.

The installed images use exactly117 pages16..132, addresses
`0x2000..0x109ff`. Uncovered bytes in that body retain the stock image tail.
Fresh full-flash and metadata backups are taken before each write; full
readback is compared afterward, including bytes outside the write range.
No COMPLETE is sent: its native path can mutate hidden metadata. ACKs alone
are not treated as programming proof. Vendor mode transitions can append
ordinary data-journal records outside the same-session comparison window.

See `firmware_dump/PRE_FLASH_AUDIT.md`, the boot/recovery/IRQ audits, and
`stock_restore/` for native protocol handoff, error hold and release validation.

## 6. Reconstruct the hardware behavior and build real QMK

Capstone disassembly, Unicorn execution and compiled C comparison were used
to recover startup/scatter initialization, exception forwarding, clocks,
GPIO bank selection, ADC sample reads, key tables, USB FIFOs and control flow.
Registers were named by observed addresses/operations where hardware roles
were unknown; an unrelated MCU HAL was not substituted.

The scan backend reads six banks and eleven candidate channels and excludes
absent positions. Original tables map those observations into physical keys.
Finite RAM probes measured released samples and held Esc+Fn on the real board.
These probes inherited warm stock/boot state and did not validate cold startup.

The build uses actual QMK core/VIA code pinned to
`f5db962110615fd263c3ebf9f0402e7c2b08fbe4`, generic ChibiOS ARMv6-M startup,
and recovered custom peripheral code. Arm GNU14.3.1 builds the ELF at
application base`0x2000`. Stack/data/BSS and27 original-boot exception
forwarding paths were checked against the actual linked ELF. Synthetic
key-report and VIA tests exercised the real compiled core, not substitute
keyboard logic. Transient EEPROM stores VIA settings in RAM only.

Tools include `recover_startup_ram.py`, `recover_scan_tables.py`,
`qmk_port/build_firmware.py` and the platform/scan/USB/VIA validation scripts.
Keystone assembled small diagnostic stubs; hashes bound generated payloads,
source/build manifests, validation results and physical trial logs.

## 7. Keep failed physical trials and revise the model

Artifact directory timestamps are UTC. The important physical sequence is:

| Trial | Observation and follow-up evidence |
|---|---|
| Initial stock rewrite | `stock_restore/live_20261103T055849Z/result.json`: stock body/readback and original interfaces verified |
| First QMK | `qmk_flash/live_qmk_20261103T062706_170286Z/result.json`: correct write/readback, no QMK enumeration; Esc-alone recovery, then `live_rollback_20261103T064616_159843Z` |
| Startup-corrected QMK | `qmk_flash/live_qmk_20261103T070202_026538Z/result.json`: still no enumeration; Esc recovery, then `live_rollback_20261103T070503_261490Z` |
| Diagnostic V1 | `qmk_flash/live_qmk_20261103T073628_065587Z/result.json`: automatic boot return; trace and verified stock restore in `live_rollback_20261103T073830_059181Z` |
| Diagnostic V2 | `qmk_flash/live_qmk_20261103T075452_444196Z/result.json`: QMK keyboard+VIA enumerate and live communication/remapping pass; left installed |

The audit identified concrete port differences: omitted factory clock/trim
setup, omitted original startup waits, short versus long USB reset delays,
an early key check that stopped on its first empty scan, missing raw-event4
endpoint setup, and cached IRQ status where the original re-read before ACK.
Regression tests compared ordered native/compiled operations and used old-code
negative controls. Correcting a genuine discrepancy was not called proof
that it alone caused the physical failure.

Diagnostic V1 recorded256 bytes at`0x20003000`, an absolute5000-SysTick
deadline, IRQ counts, USB events and faults. It reached main, counted5000
ticks, recorded one clean auxiliary IRQ and no primary USB events, then
returned to native boot. The trace was retrieved during stock rollback.
This physically narrowed the problem before normal control traffic and
demonstrated automatic diagnostic recovery on that trial.

Further native comparison found a shared startup sequence
APP`0x4a9c`/BOOT`0x5d0` and a missing auxiliary bit7 acknowledgement at
`0x40017f58`. The shared sequence gates`0x80000`, starts`0x40015000` and
polls status with the original101-read bound; a zero final status stays
nonfatal, matching the original caller. Its precise hardware role remains
unidentified. The periodic watchdog service targets a separate block.

V2 added both corrections and more trace fields. Enumeration then succeeded.
Because both changes were included together, their individual necessity or
sufficiency was not experimentally isolated. The native timed-resume branch
is still not fully implemented. A proposed RAM-only full USB takeover was
not executed: the verified loader was too small and native reinitialization
contained unbounded waits (`qmk_flash/ram_usb/feasibility.json`).

## 8. Reproduction and evidence lookup

Work on a copy of the workspace when reproducing historical builds. Current
scripts and manifests pin the latest target, while old images/proofs are
retained in `qmk_flash/*trial_artifacts/` and `qmk_port/build/flashed_*`.
Building a historical source with a newer script is not necessarily an exact
reproduction. The successful ELF is also stored as a SQLite BLOB.

Representative **offline** build/check commands from the workspace:

```powershell
$novaPython = '<LOCAL_USER>\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $novaPython qmk_port/build_firmware.py --via --diagnostic
& $novaPython qmk_port/platform/validate_firmware_elf.py --via --diagnostic
& $novaPython qmk_port/usb/validate_usb_device.py
& $novaPython qmk_port/runtime/validate_usb_diagnostic.py
& $novaPython qmk_flash/read_diagnostic_trace.py --self-test
& $novaPython audit_documentation.py
```

Some validators require both basic and VIA diagnostic builds; compile the
basic variant with `build_firmware.py --diagnostic` when reproducing them.
Check each script's source/arguments: older `*_live.py` experiments can open
hardware immediately. They are evidence, not an unattended replay recipe.
The live writer is `qmk_flash/flash_firmware.py` with explicit`--execute` and
mode`qmk` or`rollback`; do not blindly replay it on the now-working board.
Rollback requires the pinned bootloader/body/metadata state. These are
device-specific research tools, not a general production flasher.

Database tables preserve different kinds of evidence:

| Table | Contents |
|---|---|
| `findings` | Append-only conclusions, corrections and physical outcomes; early entries can be superseded |
| `decompiled`, `functions`, `edges` | Original host-side reverse-engineering material |
| `dynamic_capture`, `usb_commands`, `usb_protocol_notes` | Host protocol/capture observations |
| `diagnostic_experiments` | Experiment evidence JSON and source references |
| `firmware_dumps` | Verified firmware bytes, bases and SHA256 hashes |
| `firmware_builds` | Exact ELF bytes keyed by hash, with build manifests |
| `porting_evidence_artifacts` | Text artifacts keyed by path AND hash, retaining multiple revisions |

Useful SQLite queries:

```sql
SELECT id, topic, finding FROM findings ORDER BY id;
SELECT sha256, file_path, kind FROM firmware_builds;
SELECT path, sha256, recorded_at FROM porting_evidence_artifacts ORDER BY recorded_at;
SELECT name, base_address, byte_length, sha256 FROM firmware_dumps;
```

Raw captures, some large binaries and intermediate files also live outside
SQLite. The database is not a replacement for the complete workspace. The
older `ranked_nova_recovered_firmware_bundle.zip` predates QMK success and
must not be described as a current complete backup. Nothing in this update
publishes or commits these local records to GitHub.

## Remaining limits

The exact MCU part, keys for other untested profiles, original source and full
memory/OTP coverage remain unresolved. User-confirmed operation and the listed live
checks do not establish all-key, calibration, cold-power, suspend/resume,
long-duration or production reliability. RGB/vendor features and persistent
VIA storage are not complete. Historical reports retain their original
observations; this guide and later hash-bound physical evidence supersede
their obsolete blanket conclusions.
