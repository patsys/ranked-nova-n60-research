# Ranked Nova N60 QMK research build

The actual QMK keyboard core now links with a recovered custom platform into
`build/firmware/nova_qmk_research.elf`. This is an **offline research firmware
build, not a hardware-validated release**. No keyboard was accessed, erased,
or flashed during this build work.

An optional VIA variant now builds with `python qmk_port/build_firmware.py --via`
to `build/firmware_via/nova_qmk_research.elf`. It includes actual upstream VIA,
three dynamic layers and a32-byte Raw HID interface. Settings are RAM-backed
and disappear on restart. Load `via/nova_research.json` as a custom definition
when testing a compatible device; loading JSON does not install firmware.
The definition shows all62 keys in diagnostic bank/channel order.
See `platform/VIA_BUILD.md` and `via/README.md` for details.

## Build and inspect

```powershell
. ./.build-tools/env.ps1
python qmk_port/build_firmware.py
python qmk_port/platform/validate_firmware_elf.py
python qmk_port/scan/test_qmk_pipeline.py
```

`build_firmware.py` compiles actual upstream QMK keyboard/action/layer/keymap,
report/host, debounce and transient EEPROM sources. It links real upstream
ChibiOS generic ARMv6-M startup, the recovered analog acquisition and USB
control/IRQ implementations, and the custom runtime. ChibiOS startup is used
without claiming an existing matching MCU HAL. The ELF has no unresolved
symbols. Its map, symbols and build report are beside it. No upload tool is
invoked, and no installable `.bin` is exported.

Tools are local to `.build-tools`: ARM GCC, GNU make, MSYS2 bash and QMK CLI
in a supported uv Python environment. See `.build-tools/README.md`,
`toolchain_manifest.json` and `setup.ps1` for versions, checksums and setup.
Offline emulator dependencies are in `.tools`; validation scripts add this
path themselves.

## Implemented behavior

- Real QMK `keyboard_setup`, `keyboard_init` and `keyboard_task` runtime.
- Six analog bank rows and eleven channels, with62 populated positions.
  Acquisition initialization and14 scan cases match original-code MMIO and
  delay-argument traces. QMK custom matrix hooks use this acquisition backend.
- Three fallback layers from original firmware tables. FF/FE selectors map to
  momentary QMK layers2/1 so FF retains priority. All62 base positions have
  standard key usages or selectors.15 alternate-layer vendor action slots
  remain disabled (`KC_NO`); RGB/vendor settings are not implemented.
- Boot-keyboard USB descriptors matching this runtime, endpoint1 input,
  LED output, idle/protocol handling and queued keyboard reports.
- USB controller initialization, control-transfer and IRQ state handling
  recovered from original code, with native-vs-new-C differential tests.
- Fixed application vectors at0x2000 using the original preserved bootloader's
  IPSR forwarding. Startup initializes data/BSS in a conservative subset of
  original-used RAM. The link excludes bootloader and vendor data regions.
- Original nominal48MHz clock sequence and byte-identical selected delay loop,
  plus a standard SysTick timebase. Frequency/timing remain physical assumptions.
- QMK's actual RAM-only transient EEPROM backend. Configuration does not persist
  across reset; no flash programming driver is supplied.

## Validation and practical limits

The user has since confirmed the keyboard works. Start with
[the reverse-engineering process and evidence guide](../../docs/history/REVERSE_ENGINEERING_GUIDE.md)
for the complete chronology and current limits; earlier checkpoints below
describe their particular trials.

Latest physical result (2026-11-03): diagnostic V2 is installed, enumerates as
the QMK keyboard plus VIA Raw HID interface, answers VIA queries, and passed
a reversible remapping test in an absent matrix slot. A15-second identity/
protocol observation passed. See `qmk_flash/SUCCESS_20261103.md`. Physical
typing and cold-power/suspend-resume tests remain outstanding. VIA storage
remains RAM-only; the installed image includes diagnostic timeout/fault recovery.

Physical trial update (2026-11-03): the first VIA image passed flash readback
but failed USB enumeration. Esc held during a later reconnect successfully
requested the original bootloader. Stock was then restored and fully verified;
its six original HID collections returned. See
`qmk_flash/RECOVERY_RESULT_20261103.md` for the evidence. Corrected source builds
remain offline research artifacts until separately validated on hardware.

`platform/validate_firmware_elf.py` executes the linked image startup and all27
original-boot vector forwarding paths, checking data/BSS and bounded RAM writes.
`scan/test_qmk_pipeline.py` executes the linked QMK core and real acquisition
against modeled samples/timer, checking press/release, modifier combinations,
multiple keys, function layers and selector priority. It records the tested
ELF hash. USB native differential/host tests are recorded in
`usb/device_validation.json`; acquisition comparisons in
`scan/validation_build/result.json`.

These tests model registers and sample values, not oscillator behavior, analog
sensors, electrical timing or a physical USB host/controller. Real-device
operation, update-image boot acceptance, recovery installation and exact MCU
identity remain incomplete. Early held-key emergency entry is implemented;
see `runtime/EMERGENCY_BOOT.md`. Default is any populated key held across three
consecutive scans within a bounded startup window before USB initialization.
It writes the original retained boot request
and performs a core reset. This feature is offline-tested, not installed or
validated across cold starts. The original proprietary scheduler is
replaced by synchronous QMK polling with a separate SysTick timebase.

The default build supports a basic QMK boot keyboard; `--via` adds VIA Raw HID
and runtime remapping. Neither variant implements persistent storage,
RGB/vendor actions or every original feature.
A future corrected-image hardware experiment needs separate preparation and
verification; an offline build alone does not establish flash readiness.

Evidence, relevant sources, manifests and validation results are saved in
`ranked_re.db` for continuation. The earlier component archive and standalone
clock-validation ELF remain test artifacts; they are not this full QMK build.
