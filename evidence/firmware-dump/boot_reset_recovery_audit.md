# Reset, clock and recovery-path audit after the failed QMK boot

This audit is offline. It does not send USB commands, reset the keyboard, or write firmware. The live observation supplied by the primary agent is a fully verified QMK application write followed by Windows descriptor-request failure, with neither the original application nor bootloader HID interface detected.

## What the extracted bootloader actually provides

Reset vector `0x1cd` branches through `0x1cc` to startup `0xd8`, sets stack `0x20000bf0`, executes scatter initialization `0x150`, and enters main `0x700`. There is no double-tap counter, USB request handler, reset-button sampling, or reset-cause recovery test in that pre-main instruction path. The scatter initializer clears `0x20000324..0x20000bf0`, including the RAM guard words at `0x20000754..0x2000075f`.

Main's default explicit boot request is the exact retained-register value `0x5ac396c5` at `0x4001400c`. Code `0x77c..0x7a6` recognizes it (with the captured configured-request field `0xffffffff`), selects reason2, clears the register, and enters the USB server at `0x848`. The original application function `0x3ed8` and new application's `bootloader_jump()` write this value before the ARM reset request. A CPU reset by itself does not execute those application instructions or manufacture that value.

The captured recovery pin-pair word at `0x10000700` is `0xffffffff`. The firmware therefore skips that optional two-input test. The captured patch list at `0x10000750` is enabled and valid, so the bootloader follows the previously documented path that skips application checksum validation and jumps to the application's reset pointer. An invalid/nonworking application does not thereby force a checksum fallback to USB.

## Fast power cycling or double-tapping reset

There is **no supported double-tap/power-cycle recovery sequence in the extracted code**. Tests with different initial RAM patterns, including seeded guard markers, all reach main with those markers cleared. With no explicit retained request, they select the QMK reset. A near-magic or all-ones retained value also does not select USB.

This does not establish silicon power-retention behavior. In particular, it does not claim that RAM survives power loss. It shows that even intentionally preserving RAM markers in the emulator does not activate a double-tap mechanism in this bootloader.

## Clock-failure behavior

Before testing the retained request, main writes `0x0100b1b1` to `0x40014050`, zero to `0x4001404c`, and2 to `0x40014060` (`0x710..0x71a`). At `0x722..0x736` it checks their readback. Failure branches to `0x24c`, which requests reset through AIRCR `0xe000ed0c=0x05fa0004` and waits.

That failure path does **not** write the boot-request magic or enter the USB server. A repeated clock-readback failure can therefore repeat resets before the boot request is considered; it is not a recovery trigger. Emulation confirms this with both request0 and the real boot-request magic already present.

Eight actual-code fixture cases pass in `boot_reset_recovery_validation.json`, reproduced by `audit_boot_reset_recovery.py`. They execute the original reset/scatter/main with the current prepared QMK body and captured information block, bypass only original delay `0x9bc`, and model MMIO. They stop at application reset, USB-server selection, or the reset-request routine.

## Early QMK failure hypotheses and their limits

The original application starts `0xcd80` with `0xd5f0`, then **`0xea20(4,0)`**, then original long delay argument100, auxiliary GPIO/bank initialization `0x4470`, then long delay argument300, and later ADC initialization `0x4c68`. The QMK main transcribes `0xd5f0` but omits `0xea20` and these settling intervals; it performs matrix initialization and its three emergency scans immediately before USB initialization.

The separate cold-start analysis identifies `0xea20` as a high-address configuration-driven clock/calibration sequence: it reads configuration around `0x10000234` and programs `0x4001900c/0x40019010`, updates nominal clock bookkeeping and priorities. The word at `0x10000234` was not captured. This omission is a concrete cold-start difference and a stronger lead than assuming the original nominal48MHz value alone reproduces complete clock setup. It is not yet a demonstrated cause of the physical failure.

The physical RAM acquisition test ran inside the working stock bootloader after stock operation and did not execute QMK's complete cold startup. It therefore proved the scan primitive in that state, not the missing clock/calibration sequence or cold sensor settling. The emergency hook's three scans are short and have no proven physical startup duration. Held Esc can be missed if sensor output is not ready at that point. A warm hardware reset with sensors still powered is a possible diagnostic prediction only if a real reset control is identified; auxiliary pin purpose and power sequencing remain uncertain, so success must not be promised.

The generic ChibiOS startup, data/BSS initialization and vector placement pass actual-code emulation. No direct static linker/stack-address error was identified by that test. It stops before physical clocks and peripherals, so it cannot rule out an early hard fault or other hardware-state issue. The stock bootloader forwards faults to application vectors; the QMK default fault handler does not implement stock recovery.

## Hardware ROM or USB-bus reset

The bootloader identifies itself with a `ry72xx_boot_usb_v1.0.5` string, and the live CPUID value `0x410cc200` identifies a Cortex-M0 core. Neither identifies the exact MCU package or its hardware boot straps. High addresses `0x10000600` and `0x10000234` are used as information/configuration data by this code; that is not proof of a separate callable USB ROM recovery service.

No extracted boot path shows a USB bus reset setting the retained boot-request word or requesting a CPU reset before the application runs. Windows' descriptor-request-failed placeholder (`VID0000/PID0002`) does not establish an accessible HID or vendor control channel. A standard USB bus reset must not be presented as a known CPU reset or bootloader-entry method here.

A silicon boot strap, debug port, or reset pad may exist outside the extracted software. Identifying one requires the actual MCU marking/board evidence or an authoritative device document. This audit supplies no guessed pad-short instruction and no unsupported claim of a remaining software recovery command.
