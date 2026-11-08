# Licensing notes

This repository contains materials with different origins and licenses; there is no blanket license for the entire tree.

- The flasher is maintained in https://github.com/patsys/ry72xx-flasher (GPL-3.0-or-later); the QMK platform and keyboard code in https://github.com/patsys/qmk_firmware/tree/ranked-nova-platform (GPL-2.0-or-later).
- QMK-derived and platform files retain their SPDX headers and upstream component terms.
- Research scripts written for this investigation retain the notices present in their files.
- Vendor firmware images, firmware update captures, decrypted firmware, disassembly listings of vendor code and extracted key material are not included. `evidence/MANIFEST.json` records their size and SHA-256 with `"included": false`; `docs/REPRODUCING.md` explains how to produce them from your own keyboard.
- Documentation and evidence summaries may be quoted with attribution, but this file does not grant a license for any vendor material they describe.
