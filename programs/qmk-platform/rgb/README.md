# Ranked Nova RGB Matrix driver

Latest result: corrected image installed; lights on and typing confirmed.
Red and green physical tests passed. See [the current result](SUCCESS_20261103.md)
for hashes, validation, the initial failed trial and remaining limits.

The lighting transport was recovered from the original application's SPI
initializer `5A64/E598`, frame packer `3BF8` and submit path `5A74/E558`.
It sends 269-byte frames to a separate controller; expected response byte is A5.
No secondary-controller firmware update or flash command is implemented.

The new driver uses QMK's standard custom `rgb_matrix_driver` interface. Native
VIA RGB Matrix controls provide solid color, breathing, cycle-all, brightness,
speed and color. The separate build flag is `--rgb`; ordinary builds retain
their prior feature set. The first default is dim static white. Settings remain
RAM-only. The VIA definition with the matching three-effect menu is
`qmk_port/via/nova_research_rgb.json`; its key geometry remains diagnostic.

The transport is nonblocking, retains DMA buffer ownership while busy, polls
completion without enabling IRQ11 and bounds missing completion handling.
TX/RX buffers preserve 16-byte alignment. No arbitrary peripheral access is
exposed. Cached diagnostic GET keyboard value `02 81 00` reports transport
counters and QMK RGB configuration; it does not modify hardware.

Offline proofs:

- `original_transport_observations.json`: native SPI initializer and RGB packet.
- `transport_validation.json`: 12 compiled ARM lifecycle/differential cases.
- `firmware_validation.json`: actual linked QMK/VIA color/on/off/effects cases.
- Standard Neo2 keyboard, startup, emergency, diagnostic and USB tests are
  separate RGB-suffixed artifacts. Matrix init/scan matches the working
  timing-corrected build; its 20-unit conversion window is preserved.

## Hardware chronology

First RGB image ELF `f46e44824764e55efa45d9ce9efab6d1a3840d4bfa3fc3f33c2c46ad16420992`,
body `b16f8b8459bf1bf9a367bf6e84f4de01bd3c3c1457266382268f469e088c5721`,
was flashed and fully read back with bootloader/outside-app/metadata unchanged.
Log: `qmk_flash/live_qmk_20261103T154554_498752Z/result.json`.
The controller acknowledged more than2500 frames with no transport errors, but
the user reported lights still off. This is a failed visible-lighting test,
not successful RGB validation.

The initial frame used the native fallback timing/brightness field6250. Further
inspection identified the enabled path's table and stock level9 field250.
The next trial corrects that field and validates against the enabled native
path. The initial trial is preserved under `first_trial_artifacts/`; the prior
user-confirmed keyboard image without RGB is under `baseline_before_rgb/`.
Visible lighting, real color order and keyboard coexistence must be checked
on hardware before calling the new trial successful.
