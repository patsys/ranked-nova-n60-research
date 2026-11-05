# Ranked Nova N60

Wired 62-key ISO keyboard with analog Hall-effect acquisition and an observed
RY7203-marked controller. This experimental port uses a custom bare-metal
platform; it does not claim compatibility with another MCU family.

* Keyboard Maintainer: [patsys](https://github.com/patsys)
* Hardware Supported: Ranked Nova N60 ISO PCB with the original bootloader
* Hardware Availability: [Ranked product page](https://ranked.gg/products/nova-n60-mechanical-gaming-keyboard-iso-de)

Build after setting up the QMK build environment:

    make ranked/nova_n60:default

The default keymap is a conventional ISO layout with a function/navigation layer.
It does not enable VIA. QMK firmware lint reserves `via`/`vial` keymap names, so
VIA keymaps live in external userspace; VIA keyboard metadata is maintained in
the VIA repository separately. Neo2-specific maps are outside this contribution.
The candidate enables flash-backed QMK wear-leveling on a reserved 4 KiB region.
That storage backend has not been tested on the keyboard; do not rely on saved
keymaps until physical persistence validation is complete. The custom RGB Matrix
driver supports solid color, breathing,
whole-board color cycling,
horizontal and vertical rainbow waves, and a moving rainbow chevron. LED centers
follow the ISO layout. A suspected weak blue channel on one test keyboard's Z
LED is not compensated in firmware.

## Bootloader

Hold Esc while connecting USB for the bounded startup key check. This requests
the preserved original bootloader without erasing EEPROM or application flash.
There is no confirmed physical reset button. Original stock firmware may use
a different boot entry method.

The intended standard flashing commands are:

    qmk flash -kb ranked/nova_n60 -km default
    make ranked/nova_n60:default:flash

They invoke an external `ry72xx-flasher` tool, which is not yet available as a
distributable dependency. Flashing integration is unfinished. A generated hex
file must not be sent to an unrelated flashing tool.

See [platform status](../../../platforms/ry72xx/readme.md) for memory boundaries
and validation limitations. A standard QMK CLI image with transient EEPROM has
been tested for typing, lighting and Windows wake-on-key. The default flash-backed
persistence driver still needs physical validation.
