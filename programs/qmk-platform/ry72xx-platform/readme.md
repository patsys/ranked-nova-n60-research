# RY7203 experimental bare-metal platform

This platform targets the wired Ranked Nova N60 observed with an ARM Cortex-M0
core and a `ry72xx_boot_usb_v1.0.5` bootloader. The part marking reported from a
review photograph is `RY7203 N48C-C 2214-CC`; it is not an independently verified
vendor specification. No public register reference or compatible ChibiOS HAL
has been identified. Peripheral operations therefore use a locally implemented
register backend, derived from observations of the original firmware.

The implementation reuses Apache-licensed ChibiOS ARMv6-M startup, not its RTOS
or a HAL for another manufacturer's device. QMK's normal main loop calls the
platform and protocol hooks. See the keyboard readme for current USB and feature
support status.
Optional 32-byte Raw HID uses bounded receive queues, with parsing in QMK's
normal `raw_hid_task()` hook. Personal VIA keymaps belong in external userspace.

`protocol_pre_init()` unmasks core interrupts before `keyboard_init()` so
standard Bootmagic can use the SysTick timebase. Inherited external IRQs have
already been cleared; USB IRQ4 is enabled only after its device state is ready.

## Memory and boot contract

Application vectors start at `0x2000`. The preserved original bootloader forwards
interrupts to these vectors. The linker permits application flash through
`0x19fff` and conservatively allocates SRAM `0x20000000..0x20001c4f`. This is an
observed safe allocation window, not a claim of total physical SRAM capacity.

The stock application saves four keymap layers in flash pages D5-DC and its
reset-default path erases D5-DF. Those stock settings pages and the bootloader's
separate hidden metadata are not QMK storage. A live read-only full-flash backup
found existing data in E0-F5, erased pages F6-FF, and permission bits enabled for
F8-FF. Pages F8-FF (4 KiB at `0x1f000..0x1ffff`) are the sole QMK storage
candidate. The custom driver is enabled in the candidate build, but it has only
passed generic QMK wear-leveling tests and two Nova address-guard tests; its MMIO
controller operations and physical persistence are unverified. Do not rely on
saved keymaps until those tests pass. E0-F7, D5-DF and hidden metadata stay
preserved. Details and current gates are tracked in
`contributions/via_persistence_audit.json`.

Clock setup reads the device's factory calibration word. Timing assumes the
original nominal 48 MHz operating mode; frequency has not been measured.
The analog driver deliberately uses the original delay argument convention
for peripheral sequencing. These arguments must not be described as measured
microseconds. The longer bank conversion window was physically validated on
one Nova after shorter waits caused missing keys.

## Build and validation status

    make handwired/ry7203_nova_test:default

The one-key target runs on a Nova PCB with its existing analog front end and
reports only Esc. It is not a generic digital-pin development board. The full
Nova target is being prepared separately from platform support.

A normal QMK CLI build using transient EEPROM was flashed and readback-verified
on one Nova. The user confirmed typing and lighting, and a keypress woke Windows
from Sleep. This does not validate the custom flash-backed persistence driver,
power-loss behavior, suspend current, or other hosts. Do not flash a raw hex
file with an unrelated MCU tool.

Hold Esc while reconnecting to request the preserved bootloader. Firmware update
packaging and the vendor bootloader's custom USB protocol require the external
`ry72xx-flasher` command. The normal `qmk flash -kb ranked/nova_n60 -km via`
route has passed both offline image checking and a live application flash with
full readback verification. A clean public distribution path remains to be
prepared; users need the `ry72xx-flasher` package and a private loader profile
from their own original update capture.
