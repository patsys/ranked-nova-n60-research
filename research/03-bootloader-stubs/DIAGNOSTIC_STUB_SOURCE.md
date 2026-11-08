# Read-only RAM diagnostic stub

This is source for a Cortex-M0 Thumb subroutine, based on the local
`REPORT.md`. It is not a replacement bootloader or a flashable firmware image.
It has no flash erase/program, controller access, USB driver, or upload code.
It writes only its caller-provided RAM mailbox and the stack used by compiled C.
Memory reads are disabled in the default build.

The vendor bootloader ABI, SRAM extent, CPU-visible flash mapping, stub
authentication, and response transport remain unknown. This payload is **not
drop-in compatible** with the vendor's 440-byte stub or its multiple entry
offsets. Do not substitute it in a START packet: the surrounding bootloader
could still change flash independently. Prior bootloader entry without erasure
does not establish that arbitrary update transactions are harmless.

## Build

Install an ARM GNU embedded toolchain, then run from this directory:

```powershell
arm-none-eabi-gcc -mcpu=cortex-m0 -mthumb -Os -std=c11 -ffreestanding -fno-builtin -fno-stack-protector -fno-unwind-tables -fno-asynchronous-unwind-tables -nostdlib -Wl,--build-id=none -T stub.ld stub.c -o stub.elf
arm-none-eabi-objcopy -O binary stub.elf stub.bin
arm-none-eabi-objdump -d stub.elf
```

The linker puts the entry at the observed RAM load address `0x20000000` and
rejects payloads larger than 440 bytes. This limit is an observed vendor size,
not a verified protocol limit. No vector table or reset handler is supplied.
The caller must provide a valid aligned stack, Thumb call/return context, and
an aligned 88-byte RAM mailbox disjoint from payload, stack, and bootloader RAM.
Use the ELF symbol for the function address; a Thumb function pointer has bit
zero set. No initialization runtime is required.

## Mailbox ABI (proposed, not the vendor ABI)

All fields are little-endian; offsets are bytes.

| Offset | Field | Input/output |
| --- | --- | --- |
| 0 | magic | Input: `0x524F5354` |
| 4 | command | Input: 0 = probe, 1 = read |
| 8 | address | Input: CPU-visible source address |
| 12 | length | Input: 1–64 bytes for read |
| 16 | status | Output: 0 = OK, 1 = bad request, 2 = denied |
| 20 | count | Output: bytes returned |
| 24 | data[64] | Output: cleared each call, then populated |

Pass the mailbox pointer in R0 using AAPCS; status also returns in R0.
Probe returns ASCII `ROST` without dereferencing a source address. Start any
future integration with this probe, after independently recovering the vendor
ABI and identifying unused SRAM. The mailbox pointer itself is a trusted
caller argument: this routine cannot validate SRAM ownership without a map.
Calls must be serialized; mailbox inputs must remain stable during execution.

To enable reads, rebuild with `-DREAD_BASE=<verified-base>` and
`-DREAD_SIZE=<verified-size>`. Use only a verified readable memory window,
disjoint from the mailbox. Do not include peripheral registers: even reads can
have side effects. An invalid or protected mapping can fault or hang; no fault
recovery is provided. There is no assumed OTP/key address or decryption logic.
Results remain in RAM; retrieving them requires a separately verified adapter
for the bootloader response path or a debugger.

## Validation status

Source created only. No ARM compiler was available in the workspace session,
so binary size, generated instructions, ABI behavior, and on-device execution
have not been verified. No USB commands were sent and no device was modified.
