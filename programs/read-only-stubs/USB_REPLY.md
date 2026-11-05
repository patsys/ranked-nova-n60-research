# Real USB byte reply — verified

The own stub returned decimal **42** as the actual one-byte USB reply payload:

```text
01 00 00 73 01 00 01 77 2a 00 00 00 ...
```

This is direct USB data, not a timing measurement. Raw evidence:
`../usb_number_live.json`. Only START was sent; no DATA or COMPLETE.

## Observed native reply path

Code read through the timing channel established:

```text
00000cbe: ldr r0,[r0,#0x1c]
00000cc0: blx r0                 ; enclosing handler call
00000cc2: cmp r0,#0
00000cc4: beq 0x00000cd0
00000cc6: movs r1,#5
00000cc8: mov r0,r4
00000cca: bl 0x00000bbc
00000cce: b 0x00000e70

00000bbc: push {r4,lr}
00000bbe: cmp r0,#0
00000bc0: beq 0x00000bd6
00000bc2: strb r1,[r0,#8]        ; reply payload byte
00000bc4: movs r1,#1
00000bc6: strh r1,[r0,#4]        ; payload length = 1
```

The complete transmit implementation has not been recovered, but this native
path has now produced a custom byte on the wire.

## Own probe behavior

The START entry at offset 0x13a checks incoming LR equals 0x1021 and the
enclosing handler's saved return word at SP+52 equals 0xcc3. If both match,
it replaces that RAM stack word with 0xcc9 and sets R1 to 42. Otherwise it
returns zero without changing the stack. The native handler's verified exit
restores the caller registers and jumps to 0xcc8, allowing the native reply
builder to use the proper context and custom byte through its ordinary path.

Unlike earlier no-store probes, this payload writes **one word on the RAM
stack**. It has no flash/controller access, erase, or program operation.
Offline emulation uses the actual recovered control-flow bytes, mocks only
the reply function body, and verifies the native call receives the expected
context/number. Guard-failure tests confirm no stack modification on mismatch.
Physical USB capture confirms the number independently of that emulator mock.

After the custom reply, getv still worked. The device remained in bootloader
mode, so application restoration is a separate final cleanup step. Do not
describe the original number test as already having returned to application.

Later repeated-request and bounded-read tests succeeded. The final read test
restored application mode. See `USB_READ_CHANNEL.md` for the current tool,
evidence, restrictions, and final state.
