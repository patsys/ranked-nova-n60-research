# Current status — 7 November 2026

## Working

- Second Nova N60 (bootloader v1.0.7) runs the QMK Neo2 VIA image with full Neo2 core
  layers, Shift overrides and VIA; typing, lighting and VIA settings after replug were
  reported working by the user.
- Bootloader entry the QMK way: Bootmagic (Esc while plugging in) and `QK_BOOT`
  (Fn + B in the default/VIA keymaps; both Fn keys + B in the Neo2 keymaps).
- `ry72xx-flasher` 0.2.0 supports bootloader v1.0.5 and v1.0.7, uses its own open-source
  RAM loader and sets the application checksum word that v1.0.7 verifies. Published:
  https://github.com/patsys/ry72xx-flasher
- QMK upstream candidate (platform + keyboard + toolchain fix) on
  https://github.com/patsys/qmk_firmware/tree/ranked-nova-platform. `qmk lint`, `qmk format-c`, unit tests pass; builds with
  GCC 14.3 and QMK's GCC 15.2 toolchain.
- Personal keymaps: https://github.com/patsys/qmk_userspace (GitHub Actions builds
  against the platform branch).

## Resolved since 5 November

- **Authored loader failure** ("every other program word erased"): `flash_go` polled the
  busy bit one instruction after the start bit, when STATUS still reads `0x1`; the next
  word then redirected the running operation. Measured on a scratch page, reproduced and
  fixed (poll bits 1:0). The QMK flash driver received the same change. See
  `docs/BOOTLOADER_V107.md`.
- Bootloader v1.0.7 identified and supported (different stack frame, relocated
  dispatcher, always-on application checksum check).

## Not ready / open

- First keyboard (v1.0.5) is soft-bricked since 4 November (half-erased application,
  SWD pad damaged); see the experiment log.
- QMK PR not opened: keyboard photos, maintainer feedback on a new bare-metal platform
  and on the handwired/onekey requirement (no RY7203 development board exists).
- The fixed loader is validated on v1.0.7 hardware only; on v1.0.5 in emulation.
- Vendor material: earlier commits in this repository contain vendor firmware dumps and
  captures; see `docs/SAFETY_AND_PROVENANCE.md`.
