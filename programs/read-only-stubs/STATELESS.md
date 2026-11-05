# Stateless START probe

`stateless.bin` is our own 440-byte Thumb payload. It contains only
`movs r0, #3` and `bx lr` instructions. Known vendor entries at offsets 0,
0x24, 0x6c, 0xda, 0xfc, and 0x13a return status 3. All other halfwords
return immediately, without loads, stores, stack use, or peripheral access.
Every one of the 220 halfword entry positions passed offline emulation.
Build with `readonly_stub/build_stateless.py`.

An authorized live test used:

```powershell
& '<LOCAL_USER>\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' probe_stub_start.py --stateless --enter-bootloader
```

The bootloader answered getv before the upload. START carried our own code
and its recalculated XOR32 checksum (zero). All eight HID reports were written
successfully. The response was `01 00 00 73 01 00 01 77 04` plus zeros,
identical to the previous diagnostic payload's response.

Thus changing the entry return values did not change the observed START ACK.
This does not prove the code executed. START might only stage the code, or
the ROM might ignore/normalize its return value. It also does not establish
that a custom INFO entry can be called or its output retrieved. No CPU/memory
information was returned. No DATA or COMPLETE frames were sent.

Raw evidence: `../stateless_start_live.json`. The experiment intentionally
stopped after START rather than assuming that an ACK means execution.
If the device remains in bootloader mode, unplug and reconnect to power-cycle;
no unverified software reset or completion command was sent.
