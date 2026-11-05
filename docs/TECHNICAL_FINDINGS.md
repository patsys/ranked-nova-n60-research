# Technical findings and confidence

| Topic | Finding | Confidence / limit |
|---|---|---|
| Product | Ranked Nova N60, 60% ISO/DE, USB IDs `3532:a0a3` application and `352d:1101` bootloader | Directly observed on this device. |
| CPU family | ARM Thumb/Cortex-M0-class behavior and RY72xx/Royuan platform family | Strong platform-level evidence; exact silicon ordering code remains unknown. Do not state a definite YC model. |
| Bootloader | Native HID updater has GETV/START/DATA/COMPLETE phases; the uploaded stub is executed in the bootloader flow | Protocol and execution behavior were measured. Exact ROM ABI details are in the stub notes; related products are not interchangeable. |
| USB replies | The custom stub can return actual bytes through a recovered native USB transmit path | Repeated changing response bytes and bounded reads support this. Early ACK-only echo tests did not. |
| Firmware view | Two 128 KiB CPU-visible reads matched and exposed Thumb code | Validates that CPU-readable view only; not a raw SWD image. |
| Update transform | Captured profile uses a recovered AES-128 master/file-key scheme and two forward AES/ECB transforms | Reproduced captured ciphertext and matched executable bytes for this update profile only. |
| QMK | A research QMK build was flashed through the bounded application-only CLI route; typing, lights, Neo2, NKRO, and a key-wake test worked physically | One keyboard/host and tested build. The custom platform is not upstreamed. |
| VIA protocol | VIA v13 communications and dynamic keymap remap work in the running build | RAM/runtime behavior verified. |
| VIA persistence | Not reliable; test slot returns to `0x0001` after reset/probe, and raw flash does not match the diagnostic-reported word | Fails current acceptance. Driver and storage layout remain experimental. |
| RGB | Solid colors and rainbow visibly worked; Z blue is weaker under stock and QMK | Consistent with a physical LED/channel defect on this board, not proof of exact component failure. |
| NKRO | Eight simultaneous keys tested after endpoint correction | Physical 8-key chord and normal typing confirmed; no broader host matrix or long soak claim. |
| Remote wake | Pressing a key woke Windows from sleep on the tested setup | Single Windows host/board; not universal suspend current validation. |

## Address convention

The application image is linked at `0x2000`; the full CPU-visible flash range is 128 KiB. Vendor settings pages D5–DF are distinct from the experimental QMK wear-leveling candidate pages F8–FF. The latter have **not** been demonstrated safe for upstream persistent VIA. See the firmware map, boot audit, and persistence audit for detailed ranges and provenance.

## Do not overstate

- The exact MCU model is unknown.
- “Full firmware read” means the CPU-visible 128 KiB view, not physical SWD access.
- A live VIA remap is not proof that it survives a cold restart.
- The stock firmware update path's AES findings do not imply all hardware versions use the same key/profile.
- Related A75/RY5088/YC-family bootloader material is comparative evidence, not a command reference for this Nova.
