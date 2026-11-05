# Implemented QMK research platform

The custom build now links real QMK quantum keyboard/action/keymap processing, the recovered analog scan backend, the recovered USB driver, the new keyboard runtime, and upstream ChibiOS generic ARMv6-M startup into one research ELF. It does not select an unrelated manufacturer's MCU or use a dummy replacement for QMK's keyboard loop.

`../build_firmware.py` compiles the explicit source manifest. `../build/firmware/build_progress.json` records compilation and link results; `nova_qmk_research.map` and `.nm` expose layout and linked functions. The main runtime calls actual `keyboard_setup`, `keyboard_init` and `keyboard_task`. This is a custom bare-metal QMK platform, not a completed ChibiOS peripheral HAL port and not an upstream-supported board.

## Startup and memory placement

`startup_nova.mk` shows how the generic ChibiOS `crt0_v6m.S`, `vectors.S` and `crt1.c` are reused with our own `cmparams.h`. `NOVA_RESEARCH.ld` derives from the licensed upstream generic region/rules arrangement and places application vectors at `0x2000`, where the original bootloader forwards exceptions. VTOR initialization and RAM vector copying are disabled. Cortex-M0 is the research instruction baseline; it is not a manufacturer/part identification or physical core measurement.

The loadable flash window is `0x2000..0x1a000`, excluding the original bootloader and vendor persistent-data region. The RAM allocation window is conservatively limited to the original startup's lower used window `0x20000000..0x20001c50`; the other observed RAM region is left unused. This is not a claim of total physical SRAM. Main/exception stack receives `0x200` bytes and process stack `0x400` bytes as explicit research budgets. Runtime stack high-water and interrupt nesting still require validation.

Generic linker heap reservation consumes unused RAM in ELF size totals. Therefore reported BSS totals include reserved heap and stack sections; the actual variable BSS range is separately checked by the validator.

## Interrupt safety and checks

The platform atomic block preserves PRIMASK using actual ARM instructions and a cleanup restore. `validate_atomic.py` executes eight compiled cases covering initially enabled/disabled interrupts, normal completion, break, early return and nesting. It verifies interrupts are masked inside and the exact previous state is restored.

`validate_startup.py` first builds an isolated real-startup fixture and confirms initialized data, zeroed BSS, privileged PSP mode and bounded RAM writes. Its fixture main is only a test and is excluded from the keyboard build.

`validate_firmware_elf.py` then loads the actual linked QMK ELF into Unicorn, executes its real startup until its real main, checks data/BSS initialization, and executes the preserved original bootloader's dispatch against 27 relevant new application vectors. It confirms the SysTick and USB IRQ4 vectors reference the linked runtime handlers, and checks loadable bytes fit inside the application flash window. It stops before main's hardware initialization and does not claim physical exception timing, clock correctness, USB enumeration, or keyboard operation.

No device access, firmware installation or flash writes are part of this build or these validation scripts. No `.bin` export/install tool is created by the build.
