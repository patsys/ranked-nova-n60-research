# Built read-only diagnostic payload

`diagnostic.bin` is 440 bytes of Thumb code and padding, generated from
`diagnostic.s` by `build_diagnostic.py`. It is distinct from the earlier C
mailbox prototype. A later authorized START-only upload is recorded below.

SHA256: `7bf78ed9a7c88d9e862532c2dd38466b723600dc9417d54cd75f64def4ff5bc8`.

## Calls

- Offset 0: returns `0x524f5354` in R0; no memory writes.
- Offsets 0x24, 0x6c, 0xda, 0xfc, 0x13a: return 2; no memory writes.
  These match observed vendor operation entry offsets, but ROM dispatch
  compatibility is unverified. There is no implementation of vendor helpers.
- Offset 0x140: custom INFO call; R0 must point to 48 bytes of verified unused,
  writable, word-aligned RAM. Returns zero in R0. Requires privileged execution
  for meaningful special-register results. No pointer validation is performed.

INFO produces twelve little-endian words:

| Byte offset | Value |
| --- | --- |
| 0 | Completion marker 0x524f5354, stored last |
| 4 | Format version 1 |
| 8 | Size 48 |
| 12 | Architectural CPUID at 0xe000ed00 |
| 16 | IPSR |
| 20 | CONTROL |
| 24 | PRIMASK |
| 28 | MSP |
| 32 | PSP |
| 36 | PC sampled inside the INFO routine |
| 40 | Incoming LR |
| 44 | Reserved zero |

No stack accesses, flash/controller writes, interrupt changes, resets,
arbitrary memory reads, or USB access are present. INFO writes only its
caller-supplied buffer. The code preserves R4–R11 and SP, and uses R0–R3 and
condition flags. CPUID reads may be unavailable under unprivileged execution.
An invalid buffer can fault or overwrite unrelated RAM.

## Offline checks

Run with the bundled Python runtime:

```powershell
& '<LOCAL_USER>\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' readonly_stub/build_diagnostic.py
```

The builder uses local `.tools` packages (Capstone 5.0.9, Keystone 0.9.2,
Unicorn 2.1.4). It checks image bounds and entry overlap, disassembles special
register instructions, and emulates all seven entry calls. Tests verify
return values, callee-saved registers, stack preservation, RAM write bounds,
buffer canaries, and expected diagnostic values using an emulated CPUID.
These checks passed; they do not verify real silicon, ROM ABI, transport
behavior, or the safety of the update transaction.

## Initial hardware integration limitations

The known upload channel is firmware-update START. The saved host-side code
and capture do not establish that the bootloader avoids erase/program
operations before or outside these stub functions. Likewise the custom INFO
entry has no established ROM invocation or USB response path. The vendor
stub calls helpers beyond its uploaded 440-byte body (at offsets 0x1b8,
0x1c4, 0x1d0, and 0x1dc); their ownership and contents are not in this artifact.

The user subsequently authorized the START-only experiment based on the
explicit erase/program routines in the original stub. No DATA/COMPLETE packets
were sent. Do not use this as a firmware image or send those packets expecting
a read-only exchange.

## Live START-only experiment

See `../boot_getv_live.json`, `../stub_start_live.json`, and
`../probe_stub_start.py` for the exact exchange and narrowly scoped sender.
The device entered bootloader and replied to getv with `version:` followed by
`a1 05 00 00 a1 04 00 00`. The original START frame's 440-byte code was replaced
with this diagnostic payload and its XOR-of-words checksum was recalculated
to `0xdac2bba8`. Eight 65-byte HID writes sent only this START frame.

Reply: `01 00 00 73 01 00 01 77 04` followed by zeros. This is consistent with
the host's expected START acknowledgement. It does not prove which, if any,
stub entry ran. The no-write probe's return value did not appear in the ACK.
A subsequent getv read failed during disconnect. The final Windows PnP check
showed the application `3532:A0A3` back with OK status for its interfaces.
The cause of the return to application mode was not established.

No firmware DATA, COMPLETE, or explicit erase/program command was sent, and
the uploaded payload has no flash writes. No flash readback was available to
prove byte-for-byte preservation. INFO has not been invoked on hardware;
the experiment has not yet returned CPU identity or execution-state data.
