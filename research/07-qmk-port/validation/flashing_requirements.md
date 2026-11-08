# Standard QMK flashing integration

The platform uses QMK's existing `flash` make target. Building and flashing a
known keyboard therefore follows the normal interface:

```sh
qmk flash -kb ranked/nova_n60 -km default
make ranked/nova_n60:default:flash
```

The host program is Python 3, with hidapi for the vendor HID transport. RAM code
on the device needs separately licensed C/ARM assembly. The tool is an external
dependency, as with dfu-util; it must not embed captured proprietary loader code
without redistribution permission. The make hook supports `PROGRAM_CMD` and
`RY72XX_FLASHER` overrides using QMK conventions.

## Gate before PR

The hook now invokes the separately packaged `ry72xx-flasher` command. Its wheel
builds and installs into a fresh local virtual environment, and the normal QMK
flash target has been exercised with the flasher in offline `--check-image` mode.
The package still needs a public source/release location and loader setup
instructions for independent upstream users. No live flash is claimed.

- A source-only distributable loader, or documented lawful user-supplied loader
  extraction; the current research loader is patched from a vendor binary.
- Parse Intel HEX with checksum, overlap, address and vector validation. Reject
  bootloader, metadata, calibration and unknown memory regions.
- Identify the supported MCU/bootloader before any application erase operation;
  refuse multiple matching devices and different bootloader revisions.
- Back up the device's original flash and hidden metadata before programming.
- Keep all page erases/writes inside the independently enforced application
  bounds. Preserve every byte outside the intended overlay.
- Verify full readback and preserved regions before boot release. An ACK alone
  is not sufficient evidence.
- On programming failure, do not reset into an unverified application. Preserve
  the existing read-only recovery session and report what the user must do.
- Document recovery, stock restore, host dependencies, supported operating
  systems and the absence of proven power-loss recovery.
- Test image parsing, device identity, bounds, short transfers, timeouts,
  verification failure and recovery through fake transports before hardware.
- Physically validate this normal QMK build and the packaged tool, rather than
  inheriting results from an older image with a different hash.

`qmk flash firmware.hex` uses QMK's separate automatic bootloader-discovery path.
It is not implemented by the make hook. The supported interface under development
is the keyboard/keymap form above; documentation must not imply arbitrary-file
autodetection until its backend and tests are supplied.

## Research implementation

The existing `qmk_flash/flash_firmware.py` is intentionally restricted to fixed
image hashes and one captured device's evidence. It is not a generic substitute
for the external command. Its successful readbacks inform the protocol and
failure handling, but relaxing its guards is not part of this integration.
