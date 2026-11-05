# Controller delay callback correction

The source in `runtime/usb_keyboard.c` now wires controller initialization to `delay_controller_long`, which calls `nova_platform_delay_original_long`. The clock-gate helper still receives `nova_platform_delay_original_units`, preserving the separate native short-delay use. No flash target or installation manifest was rebuilt or changed by this correction.

Native application0x46fc calls reset/pull-up helpers0xeea8/0xeed4. Their delay calls reach long wrapper0xdd80 with arguments1,1,6. That wrapper calls the selected raw loop with `[count<<7]`, followed by `count` calls with999. The previous runtime callback selected short0xdde8 semantics, giving raw-loop arguments `[1,1,6]` instead. That was a real timing-call mismatch; correcting it does not establish that it was the sole cause of failed physical enumeration.

Run `usb/validate_controller_delays.py` for the regression check. It compiles the actual updated runtime translation unit twice (basic and VIA), checks that the compiled USB initializer's relocation references the long callback, and links only that callback plus real delay implementations into isolated validation ELFs under `usb/delay_validation/`. These are RAM-addressed test artifacts, not keyboard firmware targets.

The script executes original0x46fc and its real long wrappers while recording raw-loop arguments, bypassing only the raw iteration loop and separately handled clock-enable routine. It executes the compiled callbacks similarly and requires identical ordered call sequences. Arguments0,1,6,10 also pass wrapper-boundary checks. A negative-control build of the previous short callback produces `[1,1,6]` and is detected as a mismatch. This validates the actual wiring and semantic difference rather than merely testing a new standalone wrapper.

Existing USB native MMIO/control/descriptor/raw-transport comparisons still pass, and the original delay-loop byte identity plus eight native wrapper cases pass. Hardware timing, analog startup, enumeration and recovery remain physical validation questions. No device was accessed and no root recovery logs were changed.
