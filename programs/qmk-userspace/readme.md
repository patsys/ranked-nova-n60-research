# Nova external userspace

Personal Neo2 and VIA keymaps for the experimental RY7203 QMK platform.
These do not belong in the upstream qmk_firmware keyboard PR.

- `neo2`: core Neo levels 1–4 with a German QWERTZ host.
- `via`: conventional ISO layout with transient VIA remapping.
- `neo2_via`: Neo2 core plus VIA remapping.

Neo2 Greek/mathematical levels 5–6 are not implemented. German-host unsupported
characters remain unavailable; no Windows Unicode helper is assumed. Settings
are volatile. RGB comes from the keyboard driver, not a personal core patch.

Set QMK_USERSPACE to this directory and build with normal QMK commands:

    qmk compile -kb ranked/nova_n60 -km neo2_via

The new standard-build integration requires independent hardware validation.
The previously installed research firmware's successful tests do not establish
this new build's behavior. Stock firmware is currently installed on the device.
