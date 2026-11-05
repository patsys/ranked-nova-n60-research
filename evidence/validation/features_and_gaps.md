# Nova QMK contribution scope and verification

## Latest physical test: 4 November 2026

The latest QMK CLI flash passed full readback and preserved the bootloader,
outside-application flash, and hidden metadata. A temporary read-only diagnostic
found why earlier persistence attempts failed: the page-gate register reads as
`0xFFFFFFFF`, so the driver’s precondition rejected page FA before issuing a
controller command. The updated driver now checks the metadata permission bitmap
and F8-FF bounds, then sets and clears the gate as the recovered stub does.

On the updated image, a VIA write to the same unmapped slot immediately returned
`0x0004`; diagnostic stage 5 reported a successful controller write, and one
user-confirmed cold restart also returned `0x0004`. The subsequent read-only
full-flash audit found a small change at `0x1F408..0x1F40C`, while the reported
write address `0x1F744` remained erased. After the probe released/reset the app,
VIA returned `0x0001`. The runtime and raw-flash evidence conflict, so
persistence is not verified and the PR gate remains closed. No erase/format
command was used. Details and hashes are in `via_persistence_audit.json` and
`persistence_backend_validation_20261103.json`.

The next candidate matches the recovered stub's page-gate clear behavior by
masking off only the selected page bit. QMK default and VIA builds, default lint,
and the offline image bounds check pass. The candidate has not been flashed;
the keyboard still needs physical Esc bootloader entry, followed by a controlled
write, cold restart, and read-only full-flash comparison.

The separate transient-EEPROM remote-wake image previously passed a one-host
Windows key-wake test with full application readback verification; its record is
`.local-flasher/remote_wake_test_20261103_01/`.

The current QMK diff contains platform registration, the RY72xx platform, the
Nova keyboard, and a one-key smoke-test target. Neo2-specific keymaps are
excluded. The QMK MSYS CLI builds through the normal QMK route with the
unmodified upstream `build_targets.py`; no generic CLI workaround is in the diff.
No PR has been created.

## Implemented in the normal-build port

- Bare-metal RY7203 selection, explicit Cortex-M0 code generation, ChibiOS generic
  startup with its license preserved, and application-only memory placement.
- Standard QMK main loop, platform/protocol hooks, timer and atomic operations.
- Custom lite analog matrix, 62 populated ISO positions, QMK debounce, the
  physically established longer conversion window, and Esc boot entry.
- QMK `bootloader_jump()` and `mcu_reset()` requests to the original bootloader.
  No replacement bootloader is installed and no bootloader flash region is linked.
- Boot keyboard USB, LED output, idle/protocol requests, queued reports, metadata
  generated from keyboard configuration and UTF-16 manufacturer/product strings.
- Optional 32-byte Raw HID, bounded packet queues and main-loop dispatch.
- RGB Matrix custom transport, DMA ownership/timeout handling, 62 LED positions,
  brightness/color/speed, solid/breathing/cycle and three spatial rainbow effects.
- Conventional ISO default keymap without VIA or personal layout behavior.
- One-key build target using the existing Nova analog hardware.
- Neo2-specific maps and VIA keymap configuration are excluded from the QMK firmware PR.
- VIA metadata remains a separate contribution to its own project.

## Local checks

The builds and evidence are local, not a published release:

- `build_full_validation.log`: local builds for the default and one-key targets; personal layout experiments are outside PR scope.
- `port_validation.json`: real linked startup, USB strings, all conventional
  base keys, modifier/layer transitions and one-key behavior with modeled ADC.
- `neo2_validation.json`: real linked Neo2 key processing and standard VIA
  commands; diagnostic-only commands are intentionally excluded.
- `rgb_via_validation.json`: 15 linked RGB/VIA checks, including spatial variation
  over time, empty LED slots, DMA alignment and oversized VIA requests.
- `timer_startup_validation.json`: masked-timer negative control and normal
  initialization with modeled interrupt delivery eligibility.

Each JSON records the actual ELF hash. Synthetic samples and timer/SPI models
are not physical electrical, USB, suspend or flash tests. Earlier physical
research-build results must not be attributed to these new ELFs.

## Still required before submission

1. Public source/release location and clean install instructions for the flasher,
   plus lawful user-supplied loader setup. The normal QMK flash target and live
   application readback now pass. See `flashing_requirements.md`.
2. Retest the corrected Nova flash-backed persistence driver on hardware. The
   prior backend failed to persist; do not claim VIA persistence or open a PR
   until an unused-slot setting survives cold power loss and a read-only full
   flash probe confirms the intended page changed without touching protected data.
3. Move appropriate regression tests into a maintainable upstream test location,
   complete the final style/schema/license audit, and split platform/test-board
   support from the Nova keyboard and external keymaps into logical submissions.

## Features requiring further hardware work

The stock utility's captured `SetMatrix` traffic writes all four keymap layers,
and the user confirms stock settings survive power loss. Static disassembly now
traces the stock save path to paired flash pages D5-DC (two 512-byte pages per
layer); the stock reset-default path erases D5-DF. This is distinct from the
bootloader's hidden metadata block. Candidate QMK pages E0-FF lie outside the
initially considered pages E0-FF were checked against a verified read-only full
flash backup: E0-F5 contain existing data and remain untouched; F6-FF are erased.
The hidden metadata permission bitmap marks F8-FF writable. Those eight pages
(4 KiB at 0x1F000-0x1FFFF) are now the only QMK storage candidate. The custom
wear-leveling backend compiles and generic QMK wear-leveling tests pass. The
first physical persistence attempt failed because no storage bytes changed; the
source now mirrors the recovered page-gate sequence and timing constants, pending
hardware validation. The separate wake-test image used transient EEPROM.
Do not repurpose D5-DF, E0-F7 or hidden metadata. See `via_persistence_audit.json`
for hashes and remaining gates.

NKRO now has a local implementation with a separate report-ID bitmap interface
on endpoint4 and a retained boot keyboard interface. It defaults on for the Nova.
Offline tests cover 7/10/20-key chords, modifiers, report submission and endpoint
backpressure, control requests and boot-protocol fallback. Final candidate
regressions and physical host rollover validation are required before release.

The first physical NKRO candidate failed to type despite working VIA. It was
rolled back with full verification, and the user confirmed typing returned.
Investigation found that the USB reset path only enabled IN0/1/2 while NKRO used
IN4. A reset-and-submit regression reproduces the missing interrupt gate on that
candidate. The corrected source adds mask0x17 and the native-style IN4 enable
at0x40017f78. Its build and strengthened USB/RGB tests pass; physical verification
of that correction is still pending. This must not be described as working NKRO.

Physical follow-up: corrected ELF
`4f78ad8b0afc2181eae8bc3ee42cb66d25abfae36b3119d4103755c622688123`
was installed with complete flash/protected-data verification. The user confirmed
normal typing including K/L/O-umlaut. Windows then observed all eight requested
keys simultaneously and their complete release. This establishes hardware
rollover beyond six keys for the tested chord. Larger 10/20-key chords remain
modeled tests; sleep/wake on this exact NKRO image still needs confirmation.
The preceding paragraph preserves the pre-trial state of the correction.

The user subsequently confirmed lighting sleep/wake and normal typing after
waking the PC externally on this exact NKRO image. A post-wake VIA query verified
protocol13 and three layers. Wake initiated by the Nova remains unsupported;
the sleep/resume pass must not be interpreted as a remote-wake pass.

Consumer/system keys and mouse reports remain unsupported; the build rejects
those report features rather than silently accepting them. USB remote wake is
implemented with host permission checks, throttled key scanning and a bounded
PHY pulse. Windows wake-on-key passed once on the transient-EEPROM QMK CLI image.
Other hosts, suspend current and persistence behavior still need validation.

Personal Neo2 layers are excluded from the QMK firmware contribution. No Windows
helper or host-side layout dependency is assumed. Hall-sensor rapid trigger and
per-key actuation settings are not invented from the existing fixed-threshold
scan path.

The Z LED's weaker blue is a suspected hardware fault reported by the user,
not a confirmed defect and not evidence for changing color order globally.

No PR has been opened. No vendor firmware, proprietary loader binary, capture,
SQLite database, token or encryption material belongs in an upstream submission.
