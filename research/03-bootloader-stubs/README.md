# 03 · Bootloader stubs and the read channel

**When:** 2–3 November 2026 · **Status:** done

Own Thumb stubs were sent in the START slot instead of the vendor stub to learn what the
bootloader does with them. A success ACK alone proved nothing, so the work went step by step:
timing probes that leak one value through the ACK delay, recovery of the caller and return
context, and finally reuse of the bootloader's native USB reply callback. That gave a real
channel returning up to 56 bytes per START, which [04](../04-firmware-dump/) uses to read the
whole flash. None of these stubs erase or program flash.

## Contents

| Path | What it is |
|---|---|
| `stub.c`, `stub.ld`, `build_*.py` | Stub sources and builders |
| `*.bin`, `*.s`, `*.disasm.txt`, `*.json` | Built probes with disassembly and build metadata |
| `block_probes/`, `caller_probes/`, `usb_read_probes/` | Generated probe families (address-specific builds) |
| `scripts/` | Host-side runners for the live probes (timing reads, LR/caller reads, USB read channel) |
| `captures/` | Results of the live probes (`*_live.json`) and the few bytes each returned |

## Reports in this folder

| Report | Topic |
|---|---|
| [DIAGNOSTIC_STUB_SOURCE.md](DIAGNOSTIC_STUB_SOURCE.md) | The RAM diagnostic stub source and its limits |
| [DIAGNOSTIC.md](DIAGNOSTIC.md), [EXECUTION_TEST.md](EXECUTION_TEST.md) | Does own code execute at all |
| [STATELESS.md](STATELESS.md), [NUMBER_READBACK.md](NUMBER_READBACK.md) | Timing channel and number readback |
| [LR_READBACK.md](LR_READBACK.md), [CALLER_TRACE.md](CALLER_TRACE.md), [BUFFER_TRACE.md](BUFFER_TRACE.md) | Recovering the native call frame |
| [USB_REPLY.md](USB_REPLY.md), [USB_READ_CHANNEL.md](USB_READ_CHANNEL.md) | The native USB reply channel |

## Next

[04 · Firmware dump](../04-firmware-dump/) reads the full CPU-visible flash through this channel.
