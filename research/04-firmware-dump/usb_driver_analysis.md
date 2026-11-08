# Original application USB driver recovery

Scope: static analysis and offline execution of `flash_cpu_pass1.bin` (SHA256 `5adca278d90a0672e05dfe5ad47d1635242f9ec0ff78827d83d9f28d6ccd8b49`). No device was opened and no firmware was installed. Addresses below are CPU addresses in the recovered application, not offsets relative to its 0x2000 base. Function names are descriptive labels added here.

## Established driver boundaries

| Address | Recovered behavior | Evidence |
|---|---|---|
| 0x312c | USB interrupt dispatcher, external IRQ4 | Application vector20 is 0x312d. Tests bits0/1 of 0x40016008, dispatches 0xebf0 / 0xf310 |
| 0x46fc | USB hardware and endpoint initialization | Calls clock-enable routine0xf0dc, configures controller and endpoint banks, calls endpoint configuration helpers |
| 0xf0dc | Enable USB-associated clock/reset domain | Calls0xd57c(2), 0xd524(0x80000000,1); polls bit0 of0x40014120, then delay0xdd80(10) |
| 0xebf0 | USB event/endpoint interrupt handling | Reads low5 bits of0x40016000; dispatches through compiler jump table; references endpoint callbacks and control state |
| 0xf310 | Additional USB event handling | Reads0x40017f58 through0xeff8 and updates device state/callbacks |
| 0xf170 | Controller command setter | `*(uint32_t*)0x40016000 = argument & 0xc0` |
| 0xf220 | Endpoint configuration setter | `*(uint32_t*)(0x40017e00 + (ep&63)*4) = value&255` |
| 0xf180 | Second endpoint configuration setter | `*(uint32_t*)(0x40017e20 + (ep&63)*4) = value&255` |
| 0xf118 | Transmit buffer submission | Waits for RAM ready flag, clears it, copies source bytes to spaced FIFO words, writes transfer length |
| 0xf3fc | Byte source to word-spaced peripheral copy | Each source byte becomes one 32-bit destination store; destination advances4, source advances1; wrapped by0x2220 /0x2228 interrupt masking helpers |
| 0xf044 | Application-facing guarded transmit wrapper | Calls0x41e8; requires result5 and0xf104 nonzero before calling0xf118 |
| 0xf104 | Software readiness gate | Returns1 iff word at0x20000424 >=100 |

The IRQ source writes are recorded exactly: on bit0, it writes current status AND2 back to0x40016008; on bit1, it writes current status AND1. Hardware write/clear semantics require further validation; these are not ordinary RAM operations.

## Transmit path recovered and executed offline

The original routine0xf118 implements the following behavior for tested endpoint values0..5:

```c
/* Descriptive pseudocode, not a complete standalone USB driver. */
wait_until_ready_or_timeout(ep); /* RAM 0x20001340 + ep*4; approximately20001 polls */
ready[ep] = 0;
uint32_t *fifo = (uint32_t *)(0x40017c00 - (ep & 63)*0x200);
for (unsigned i = 0; i < length; ++i) fifo[i] = source[i];
*(volatile uint32_t *)(0x40017ed4 + (ep & 63)*8) = length & 127;
```

The timeout loop calls0xdde8(10) and uses counter limit0x4e20. The caller0xf044 supplies additional software connection/readiness checks. The bare0xf118 itself does not validate that an arbitrary endpoint is supported or enforce a 64-byte input length; a new driver must validate these explicitly.

`trace_usb_driver_offline.py` executes the actual recovered0xf118 and0xf3fc machine code with Unicorn. All18 cases (endpoints0..5, lengths0/1/64) reached the return sentinel, cleared the selected ready flag, and produced exactly the expected FIFO stores and length-register store. Source data included high-bit bytes0x80 onward. Results and instruction addresses are in `usb_tx_offline_traces.json`.

This verifies instruction behavior under supplied ready flags and zero-filled peripheral memory. It does not emulate a USB controller, prove packet transmission on a physical bus, or validate enumeration. No original USB routines were replaced with mocked C copies for those cases.

## Initialization writes at0x46fc

After0xf0dc, the sequence includes:

| Register/address | Written value or action |
|---|---|
| 0x4001401c | 0x21 |
| 0x40017f58 | Low8 bits preserved; bit3 set by0xeed4 with delay6, then cleared by0xee94 |
| 0x40016000 | Pulse0x80 then0 via0xeea8/0xf170 with delay1 each |
| 0x40016008 | 0 |
| 0x40016010,0x4001600c | 3 each |
| 0x40017eb8 | 0x1f |
| 0x40017eb0 | 1 |
| 0x40017ea4 | 0x3f |
| 0x40017eb4 | 1 |
| 0x40017ea8 | 0x3f |
| 0x40017e04/08/0c/10/14 | 0x04/14/24/44/54 through0xf220 |
| 0x40017e20 | 0x2e |
| 0x40017e24/28/2c/30/34 | 0x04/08/28/30/3c through0xf180 |
| 0x40017f88 | 0x13 |
| 0x40017fc0 | 0 |
| 0x40017fe0 | 8 |
| 0x40017f8c | 4 |
| 0x40017f78/7c | 1 each |
| 0x40017f80/84 | 0 each |
| 0x40017f14 | 0x7f |

The ordering in original0x46fc should be retained when implementing hardware support; the table groups related writes for readability. Meanings such as FIFO allocation encoding and pull-up control are not established merely by these values.

## Endpoint and interrupt structures

0xebf0 uses0x40017e80 as its common register-bank base. Endpoint callbacks in the event path feed return values into0xf194 (IN state encoding) and0xf234 (OUT state encoding).0xf194 accepts states0/0x1000/0x2000/0x3000;0xf234 accepts0/0x10/0x20/0x30/0x40. Control endpoint0 is handled specially with shared register0x40017ed0; endpoint8 is also special. Neither should be generalized from endpoint1..5 formulas without recovering those branches.

For nonzero endpoints other than8, IN status is read at0x40017ed0 + ep*8, and OUT state at0x40017f10 + ep*8. Event handler0xebf0 iterates endpoints1..5, preserving/replaying selected length state around control handling. Static interpretation of these register accesses needs a hardware model or documentation before assigning conventional status names.

The original linear disassembly includes literal pools and compiler jump-table bytes decoded as instructions (notably0xec18..0xec28). These are data, so apparent branch targets in that region must not be treated as ordinary code without decoding the jump-table helper0x317a.

## Remaining work before a genuine QMK USB backend

1. Recover the control endpoint0 SETUP/data/status engine and exact callback return protocol. Trace0x41e8,0x2520,0x4b20 and callback tables initialized around0xf004, then locate device/configuration/HID report descriptors.
2. Decode FIFO allocation/configuration fields used by0xf180/0xf220 and recover the matching receive FIFO path; byte-to-word TX copy is established, receive behavior is not complete.
3. Recover clock frequencies and interrupt enable/priorities associated with IRQ4.0xf3a8 calls0x2ba8 for exception/IRQ priority setup, including IRQ2 andIRQ4; NVIC enable configuration remains to be traced.
4. Implement the QMK/ChibiOS USB low-level interface or another genuine supported QMK platform backend, then validate enumeration and transfers. A transmit helper alone does not constitute a working QMK port.

Exact MCU manufacturer/part remains unconfirmed. These addresses and routines are direct firmware evidence that can support a new HAL even without a marketing part name; they do not establish compatibility with an existing STM32/Sonix/Yichip SDK.
