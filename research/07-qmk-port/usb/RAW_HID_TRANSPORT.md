# VIA raw HID transport over recovered endpoints

The controller engine supports the proven original OUT endpoint3 and IN endpoint2. Named constants are in `ranked_usb_io.h`: `RANKED_USB_RAW_OUT_ENDPOINT=3`, `RANKED_USB_RAW_IN_ENDPOINT=2`, `RANKED_USB_RAW_REPORT_BYTES=32`.

The original controller configuration already initializes these endpoints. Runtime descriptors may advertise interface1 with interrupt IN0x82/OUT0x03 and32-byte reports. The low-level FIFO capacity remains64; the runtime must reject raw messages whose length is not32.

## Receive

Event13 in low5 bits of0x40016000 is endpoint3 OUT completion. The engine acknowledges mask8 at0x40017ea8, reads count low7 bits at0x40017f2c, and invokes the proven vendor receive primitive:

* FIFO base0x40017500.
* Byte reads at base+i*4, preserving original access width and stride.
* `callbacks.packet(context,3,data,length)` receives the payload.
* The engine rearms the OUT length/status register by writing127 to0x40017f2c.

The callback's data pointer is valid only during that callback. Copy32 bytes to a bounded queue in the interrupt handler and process VIA requests from the main loop. The engine does not call QMK/VIA handlers inside its IRQ path.

## Transmit

Use `ranked_usb_device_send(device,2,payload,32)` with the same interrupt serialization as keyboard report submission. The engine returnsfalse while unconfigured or while endpoint2 has an outstanding transfer; the runtime should retain its reply and retry later.

* FIFO base0x40017800.
* Each payload byte is written as one32-bit FIFO word at base+i*4.
* Length32 is written to0x40017ee4.
* Event10 acknowledges mask4 at0x40017ea4 and makes endpoint2 ready again.

The controller engine supplies transport. HID usage page/usage,32-byte report descriptors, packet queues, and VIA command dispatch belong to the runtime.

## Offline verification

`validate_usb_device.py` now compares a32-byte raw endpoint3 OUT IRQ directly against original0xebf0 ->0x287c ->0xd4d4 machine code. Only vendor command processing0xcec0 is skipped. All32 source reads have size1 at the expected word-spaced addresses; the original RAM payload is byte-exact; new C acknowledgment/rearm MMIO writes match the native sequence exactly.

The script separately executes original0xf118 for endpoint2 with32 bytes and compares all32 FIFO stores and its length store against new C. Host tests cover OUT callback delivery, endpoint2 reply submission, busy handling, and readiness restoration through event10. Existing controller/EP0 comparisons still pass. Results are recorded in `device_validation.json` under `raw_endpoint3_irq` and `raw_endpoint2_tx`.

No physical USB access, installation, erase, or persistent write occurs in these tests. Actual VIA enumeration and traffic remain hardware validation work.
