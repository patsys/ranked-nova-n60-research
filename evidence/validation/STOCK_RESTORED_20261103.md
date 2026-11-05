# Stock restored before upstream flashing-tool tests

The user requested an original-firmware baseline. The fixed, previously
validated stock rollback completed after physical Esc-held boot entry.

- Result: `../qmk_flash/live_rollback_20261103T163223_368436Z/result.json`
- Stock application SHA-256:
  `7f7f5853e7192c737be85cc00e0b21db56e8a40bd68495900002921ef914762c`
- All 117 application pages were acknowledged, then the entire 128 KiB flash
  matched the expected same-session overlay.
- Bootloader, all bytes outside the application and hidden metadata matched
  the pre-write backup.
- Six original application HID interfaces returned; no bootloader interface
  remained. QMK/Neo2 is not currently installed.
- No COMPLETE command was sent. The test used the existing pinned research
  flasher, not the new QMK make hook or a distributable general-purpose tool.

Full pre-write/readback backups and the restored target remain local. They are
not candidates for upstream submission. This restore verifies the stock baseline
and existing research rollback path; it does not establish the new integration's
physical behavior or power-loss recovery.
