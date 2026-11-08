# QMK platform and build assessment

Analysis date: 2026-11-02. Offline firmware/source analysis only; no device access, installation, or flash operations. No SQLite changes by this analysis task.

## Result

The recovered binary is sufficient evidence to continue implementing hardware support. It does not yet match a demonstrated existing QMK platform. A working keyboard firmware cannot currently be produced just by choosing a supported Cortex-M chip with a similar memory address. The useful path is a small, evidence-based hardware support package, followed by QMK integration.

The MCU manufacturer/part remains unconfirmed. The Cortex-M0/M0+ inference is not a chip identification. No AGENTS.md was found in the workspace, QMK checkout, or checked parent directories.

## Actual checkout and tools

- QMK checkout HEAD: `f5db962110615fd263c3ebf9f0402e7c2b08fbe4`. Working tree clean during assessment. Sparse checkout includes platforms, quantum, tmk_core, drivers, builddefs, data, util, lib and docs.
- Every QMK submodule is uninitialized: ChibiOS, ChibiOS-Contrib, printf, LUFA, V-USB, pico-sdk, googletest and LVGL. ChibiOS revision is `6170ddf92d55be54c89b708d1882eea229edeb2c`; ChibiOS-Contrib is `5a9ad82b6ba4f649cdb800e8c2bbc9be2d3ce767`.
- `gcc.exe` is available at `C:\Strawberry\c\bin\gcc.exe`, but `gcc -dumpmachine` returns `x86_64-w64-mingw32`: it is a Windows host compiler, not the firmware compiler.
- `make`, `arm-none-eabi-gcc`, `clang`, `cmake`, `ninja`, and `bash` were not resolved on PATH. The WSL executable returns installation/help output for `wsl --list --quiet`, rather than a usable distribution listing. WSL availability should not be assumed.
- No dependency installation or fake/stub QMK build was performed. These are environment observations, not proof that installing tools is impossible.

## Platform comparison against primary headers

The exact ChibiOS-Contrib Git revision above was inspected through GitHub's recursive tree API and raw primary headers. This avoids treating empty submodule directories as evidence of absent upstream drivers.

| Candidate | Primary register definitions | Comparison with recovered firmware |
|---|---|---|
| SN32F240 / SN32F260 / SN32F290 | USB `0x4005c000`; flash controller `0x40062000`; GPIO banks `0x40044000`, `0x40046000`, etc. | Does not match verified native flash controller `0x40013000`, recovered USB control `0x40016000` or GPIO `0x40018000`. Existing Sonix support cannot simply be selected. |
| WB32FQ95xx | USB `0x40014000`; FMC `0x40017800`; GPIO banks `0x40000000`, `0x40000400`, etc. | Some literals overlap the dump, but the combined flash/USB/GPIO map differs. A shared literal is not evidence of compatibility. |
| WB32F3G71xx | Same inspected GPIO bank locations as WB32FQ95xx, flash alias `0x08000000`. | No demonstrated match. |
| AT32F415 | USB OTG FS `0x50000000`, STM32-like GPIO/flash-controller bus offsets. | No demonstrated match to the recovered controller behavior. |

Primary header paths, relative to [the exact upstream revision](https://github.com/qmk/ChibiOS-Contrib/tree/5a9ad82b6ba4f649cdb800e8c2bbc9be2d3ce767):

- `os/common/ext/SONiX/SN32F2xx/SN32F240.h`, `SN32F260.h`, `SN32F290.h`.
- `os/common/ext/CMSIS/WB32/WB32FQ95xx/wb32fq95xx.h` and `WB32F3G71xx/wb32f3g71xx.h`.
- `os/common/ext/CMSIS/ArteryTek/AT32F415/at32f415cx.h`.

ChibiOS-Contrib does contain SN32 ports even though this QMK revision's `platforms/chibios/mcu_selection.mk` does not expose an SN32 selection. This is not a complete survey of every possible chip/SDK; it rules out straightforward substitution of these frequently suggested keyboard families.

## Integration requirements grounded in the local source

`platforms/chibios/platform.mk` selects startup, ARM context port, platform/HAL files and a board definition. `platforms/chibios/gpio.h` implements QMK pin access through ChibiOS PAL (`palSetLineMode`, `palReadLine`, etc.). `tmk_core/protocol/chibios/usb_main.c` uses the ChibiOS USB driver and calls `usbStart`. Consequently, board JSON and VID/PID values alone cannot supply this device's missing peripheral behavior.

The upstream policy in `docs/platformdev_selecting_arm_mcu.md` expects new MCU-family support in ChibiOS/ChibiOS-Contrib for upstream QMK acceptance. A private research fork can be developed before upstream acceptance; the policy does not prevent local development.

## Evidence now available for implementing that support

Parallel analysis has recovered concrete driver structure: USB control `0x40016000`, endpoint banks `0x40017e80`, packet FIFOs `0x40017c00`; GPIO banks at `0x40018000` with bank selection by pin upper bits; an analog 6-by-11 scanning structure. These details belong to the USB and key-scan analysis reports and need their function-level evidence retained before driver implementation.

`startup_ram_analysis.json` supplies a stronger startup/RAM basis than the initial SP alone: original initialization produces 1364 initialized bytes at `0x20000000`, zeros `0x20000554..0x20001c50` and `0x20003000..0x20003718`, and reaches original main `0xcd80`. These accessed regions are not proof of the complete RAM size or free QMK stack/heap budget.

## Concrete sequence toward a meaningful build

1. Implement register definitions only where native code supplies proven offsets/semantics; keep inferred field names marked as such.
2. Supply startup/vector behavior, clock/tick setup and linker placement consistent with the original app at `0x2000`, preserving bootloader and vendor data regions. Confirm interrupt-vector remapping rather than assuming VTOR exists on the inferred core.
3. Implement USB low-level driver with reset, setup/control transfer, address/configuration, endpoint IN/OUT and interrupt handling. A single working native reply callback is not the complete application USB driver.
4. Implement analog scan acquisition and map its 66 positions into QMK matrix state; recover thresholds/calibration before assuming digital row/column scanning.
5. Integrate minimal QMK keyboard support, initially without RGB and persistent writes. Add VIA raw-HID support and an explicit persistent-storage policy afterward.
6. Install an ARM cross compiler and usable make environment in the workspace, initialize the needed QMK submodules, then compile and inspect ELF sections/vector table. A compile succeeds only after those hardware implementation requirements are satisfied; compilation alone does not demonstrate operation.

Bootloader plaintext delivery was verified previously with program/erase callbacks disabled. It proves an input-data route, not that a replacement image passes all boot checks or is safe to install. No installable QMK image is claimed by this report.
