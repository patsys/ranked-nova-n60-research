# Missing-key acquisition fix — 3 November 2026

The user reported many missing keys after installing Neo2, including physical
German K/L/Ö (Neo r/t/d). The complete live VIA map matched the compiled default;
this was not a wrong Neo keycode assignment.

## Diagnosis and evidence

A temporary volatile F23/F24 remap produced no selected host events for L/Ö and
was restored. The legacy RAM-only scan then returned zeros everywhere after
cold boot, so it could not isolate this fault. That stub lacks the complete
running application's initialization and must not be treated as equivalent.
Its cleanup returned to QMK. Windows initially blocked bootloader HID startup
with Code 10; a physical reconnect on another port resolved access.

A diagnostic-only read query was added through `via_command_kb`, backed by
cached samples in the keyboard matrix implementation. It performs no sensor
MMIO reads or writes. See `qmk_port/runtime/SENSOR_DIAGNOSTIC.md`.

The user held K/L/Ö, then A/S/D. With the original five-unit conversion window,
K/L/Ö mostly returned 0–4 with sporadic peaks around 130–134. Across 46 selected
held snapshots, none had a debounced press for any of those keys. A/S/D sustained
132–133 and were debounced active in all 52 comparison snapshots.

The bank-high delay between conversion trigger and bank disable was increased
from 5 to 20 original helper units, through the keyboard configuration macro
`NOVA_SCAN_CONVERSION_SETTLE_UNITS`. These units are not measured microseconds.
The recovered acquisition implementation retains a five-unit default outside
this board configuration. No threshold, register value, scan read order or
Neo mapping was changed. Exactly one application flash byte differed from the
preceding sensor-diagnostic image. Eight compiled differential cases verified
the six per-bank delay changes and otherwise matching init/scan behavior under
synthetic samples. This is explicitly a timing differential, not an assertion
of exact original timing equivalence.

After installation, K/L/Ö sustained 133–134 and both raw and debounced rows were
active in all 47 selected held snapshots. A/S/D remained active in all 50
comparison snapshots. The user confirmed that the previously failing keys now
work, then reported “looks all good.” This supports insufficient conversion
settling time as the cause of this regression. Exact silicon conversion-ready
timing was not measured with instruments, and all 62 keys were not individually
certified by an automated physical test.

## Installed image and checks

- VIA ELF SHA256: `8fbed3bc051b69ae5005ae2293566ffaeb2c4b91fbf36e7c53c0539bc700c711`.
- Application body SHA256: `a924b79044fa9c26b92a6ade993b0a74f6f7b1ddbe5d73d3060ff302aa241f80`.
- Flash log: `qmk_flash/live_qmk_20261103T150326_175072Z/result.json`.
- All 117 application pages acknowledged; full 128 KiB readback matched the
  expected overlay. Bootloader, all outside-application flash and hidden
  metadata were unchanged. No COMPLETE command was sent.
- Keyboard and VIA interfaces enumerated. Final read-only VIA verification
  confirmed protocol 13, three QMK layers and all 396 Neo2 map bytes, followed
  by a 15-second query soak.
- Offline checks passed: 114 keyboard/228 VIA cases in the VIA build, 113
  keyboard cases in the basic build, 41 emergency, 22 diagnostic, 8 transport,
  29 flash-host cases, startup/vector checks and native bounded programming
  protocol validation.
- QMK core remains unmodified. Neo2 stays in its separate keymap with standard
  Key Overrides and the local dual-held Mod3/Mod4 hook.

Raw captures: `sensors_20261103T145709_281700Z.json` (before) and
`sensors_20261103T150535_050808Z.json` (after), under `qmk_port/neo2/`.
Selected-window statistics: `timing_fix_comparison.json`.
Prior images and proofs remain in `pre_timing_trial/`, `pre_sensor_diagnostic/`
and `working_firmware_before_neo2/`. SQLite retains the evidence revisions.

Neo2 scope is unchanged: German QWERTZ host, helper-free core levels 1–4,
unsupported typography disabled, levels 5/6 absent and volatile VIA edits.
