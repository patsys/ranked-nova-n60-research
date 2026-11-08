# Public bootloader research — checked 2026-11-02

## Closest match

https://github.com/svumo/DrunkDeer-Control/blob/main/docs/firmware-flash-research.md

Author's reverse engineering and capture: DrunkDeer A75 Pro has bootloader
352D:1101, enters with 04 A5 01, and uses getv over interrupt endpoints 04/84.
Its updater uses UsbHid_v1.2.7.dll and Ry_Online_Update branding. The captured
variant has a longer version reply and different operational framing than
ours. This strongly suggests shared updater lineage, not identical ROM or
interchangeable commands. It does not document our stub's USB-send API.

## Related, different protocols

https://github.com/dot-agi/ry5088-flasher/blob/main/docs/protocol.md

RY5088/AT32F405: bootloader 3151:502A and HID Feature reports. Different from
our observed 352D:1101 interrupt transport; not a direct implementation guide.

https://github.com/dniminenn/sharkfin/blob/master/docs/PROTOCOL.md

Documents a related YC-family bootloader extracted from a firmware image,
but its BA C0 / BA C2 protocol differs from our getv and s/w framing. Relevant
as comparative research, not evidence of our device's MCU or ROM layout.

No exact public reference for our 440-byte stub ABI, ROM USB transmit routine,
or 40013000 flash-controller implementation was located in this search.
This is a search result, not proof that such material does not exist.

Existing MCU identification remains provisional. Public sibling documentation
does not justify assigning a specific chip model to the Nova keyboard.
