# VIA research build

Run `python qmk_port/build_firmware.py --via` with the workspace Python runtime. The VIA build goes to `qmk_port/build/firmware_via`; the basic keyboard build remains in `build/firmware`. The pre-VIA basic ELF and metadata are additionally preserved in `build/basic_before_via`.

The VIA image compiles actual upstream `via.c`, `dynamic_keymap.c`, `raw_hid.c`, `nvm_via.c`, `nvm_dynamic_keymap.c` and `send_string.c`, with three dynamic keymap layers and 32-byte raw HID packets. Actual upstream VIA `raw_hid_receive` and `raw_hid_send` are retained in the final ELF by the runtime's raw USB transport. The standard keyboard quantum loop and analog acquisition remain the same genuine implementations.

Storage uses QMK's **transient EEPROM driver**, backed by a 1024-byte RAM array. No flash EEPROM emulation, native vendor config writer, erase routine or flash programmer is included. VIA edits therefore disappear at power loss/reset. Upstream static storage-layout assertions pass, including the required space after the 396-byte three-layer keymap for dynamic macros. The VIA date magic uses the reproducible research build date in `version.h`.

The linker still confines every allocated byte to the conservative original-used lower RAM window, ending `0x20001c50`. With the current raw USB queues and VIA guard, initialized data occupies 40 bytes and variable BSS occupies 1656 bytes; heap begins `0x20000ca0`, leaving 4016 bytes to the allocation-window end. Main/exception and process stacks remain separately reserved at 512 and 1024 bytes. These are research budgets, not measured physical stack margins or total MCU SRAM claims.

`validate_firmware_elf.py --via` checks this separate image's actual startup, initialized data, BSS, load placement and 27 preserved native bootloader forwarding paths. It does not perform hardware USB enumeration. Runtime VIA protocol/remap and transport tests are separate evidence.

The toolchain reports four libnosys warnings for `_close`, `_lseek`, `_read` and `_write` while scanning standard-library archive members referenced by the send-string dependency graph. The warnings are preserved in `build_progress.json`. Those system-call functions, `rand` and `_impure_ptr` are discarded from the final linked symbol table, and the final ELF has no unresolved symbols; the application does not provide a file I/O service.

This remains an offline research ELF. No device access or firmware installation is performed by either build mode.
