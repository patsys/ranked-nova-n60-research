# Verified two-way USB read channel

The own RAM stub now returns real USB data. Verified milestones:

- Fixed number 42 returned as payload byte `2a`.
- Changing probes returned 43, 42, 43 over repeated START requests in one HID
  session. This establishes that the new code is loaded and executed each time.
- Six code bytes at 0x101c returned `ff f7 06 f9 33 e0`, exactly matching
  independent timing reads. They decode to `BL 0x22c; B 0x108a`.
- A 32-byte USB read at 0xbbc matched the first 16 timing-read bytes and
  recovered the remainder of the native reply builder.

Evidence: `../usb_number_live.json`, `../usb_repeated_live.json`, and
`../usb_code_read_live.json`. These are USB payload bytes, not timing estimates.

## Tool

`../usb_read_channel.py` provides `Reader.open()`, `Reader.read(address,length)`,
and `Reader.close()`. Example from the workspace:

```powershell
& '<LOCAL_USER>\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' usb_read_channel.py --address 0x101c --length 6
```

Without arguments it runs the independent-code comparison and native-builder
read described above. With arguments it prints the requested hex bytes and
saves a request-specific JSON log. Parameters are embedded in a generated
read-only ARM request stub; one byte is returned per START. It is not a
permanently installed service or a replacement firmware.

Reads are restricted to the inspected code windows 0x200–0x2ff,
0xb00–0xcff, and 0xf00–0x10ff, with a maximum of 256 bytes per command.
The live version reply must match the observed `a1050000 / a1040000` pair.
The payload checks LR 0x1021 and saved LR 0xcc3 before modifying the one
caller-stack return word at SP+52. It then reads the selected code byte and
routes through the native one-byte reply builder. Earlier guard-failure tests
confirmed no stack modification when those identities mismatch.

## Writes and limits

This is read-only with respect to flash. The payload modifies one verified
return word on the **RAM stack**, and the native reply routine writes its
RAM output buffer and operates USB. No flash controller access, erase/program
routine, firmware DATA, or COMPLETE packet is used by this read tool.
Offline emulation verifies the exact recovered control flow and bounded stack
writes; it mocks the reply helper body. Real USB data independently verifies
the end-to-end operation.

Application restoration uses the previously verified ordinary no-op START,
then getv/disconnect transition. The demonstration finished with six
application HID collections and zero bootloader interfaces. This confirms
application USB enumeration; a full flash integrity/keyboard functional test
was not performed.

The current interface is one output byte per request, limited to this
bootloader build and inspected code windows. A full plaintext firmware dump,
arbitrary-address service, key extraction, and a general replacement firmware
have not been implemented or claimed.

## Later block-reader and firmware result

The separate `../usb_block_reader.py` now returns up to 56 bytes per reply
using the native transmit callback at context+0x214. It modifies the guarded
RAM-stack return word and native RAM reply buffer, with no flash operations.
Its CPU read range is bounded to 0x00000000–0x0001ffff. The original one-byte
tool above retains its narrower inspected-code limits.

`../dump_firmware_live.py` used that block reader to acquire two identical
128 KiB CPU-visible snapshots. The bootloader/application binaries and
linear Thumb disassembly are in `../firmware_dump/`; see its README. This
later result supersedes the earlier statement above that a full dump had not
been implemented. It does not constitute a general replacement firmware or
an identification of physical flash encryption/key behavior.
