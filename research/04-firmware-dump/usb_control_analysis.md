# USB control, descriptors, and receive-path recovery

All work here was offline. No device was opened or flashed. The original binary SHA256 is recorded in `usb_driver_analysis.md`.

## Startup decompression resolves actual USB structures

Executing the original scatter loader0x2284 until its handoff to0x20e0 reconstructed initialized RAM without guessing pointers. Its table is at0x10614..0x10644:

| Source | Destination | Output bytes | Original handler |
|---|---|---|---|
|0x10644|0x20000000|0x554|0x22a8 decompressor|
|0x10908|0x20000554|0x16fc|0x31a4 zero-fill|
|0x10908|0x20003000|0x718|0x31a4 zero-fill|

The saved16KiB RAM snapshot is `qmk_port/usb/original_initialized_ram.bin`, SHA256 `2c85960d0f7b83dd47969acb5632257f1996240c3fb6a9e9a64dee9534aadced`. This includes the output regions above and otherwise zeroed emulated RAM; it is not a live RAM dump.

Original0xf004 installs pointer slots at0x20000510/514/518: control context0x20001418, class callback table0x200003cc, device callbacks0x200003fc. The initialized class table supplies init0x46fd, configure0x4859, class request dispatch0x4515, device/config/string descriptor callbacks0x45b1/45a1/46d9, and EP0 maximum packet size8 in table+0x2c. Callback pointers include the Thumb low bit.

Descriptor pointer/length pairs at0x20000378 onward resolve to:

| Descriptor | CPU address | Bytes |
|---|---|---|
|Device|0x104a7|18|
|Configuration|0x104b9|66|
|HID report interface0|0x104ff|65|
|HID report interface1|0x10540|211|
|HID descriptor interface0|0x104cb|9|
|HID descriptor interface1|0x104e4|9|
|Language|0x104fb|4|
|Manufacturer `Ranked`|0xf5c7|14|
|Product `Nova 60% Keyboard`|0xf5d5|36|
|Serial `rankednova`|0xf5f9|22|

The device descriptor confirms VID0x3532, PID0xa0a3, bcdDevice0x0004 and EP0 size8. The configuration contains two interfaces: boot keyboard interface0 with interrupt IN0x81 size8; composite HID interface1 with interrupt IN0x82 and OUT0x03, size64 each. Interface1's report descriptor supplies additional collections/reportIDs. Extracted binary descriptors and byte hashes are in `qmk_port/usb/`; they are evidence of the vendor protocol, not proposed QMK descriptors.

## Original control response executed byte-for-byte

`firmware_dump/recover_usb_control_offline.py` installs the three pointer assignments from0xf004 without pretending to run clock/controller initialization. It writes a requested SETUP packet into word-spaced setup registers and executes original0xdf90. That function reads eight bytes from0x40017fa0 + i*4 into the control context, dispatches through0x2364 or0x2bec, and returns through0xd5a4. Descriptor callbacks and the0x2520 EP0 IN chunk sender remain original machine code.

Twelve descriptor requests passed: device first8/full18; configuration first9/full66; both HID report descriptors; both HID descriptors; language, manufacturer, product, and serial strings. Full responses matched original bytes exactly, including8-byte packet boundaries. Examples: device response `[8,8,2]`, configuration `[8,8,8,8,8,8,8,8,2]`, report descriptor1 twenty-six8-byte packets then3 bytes.

For additional IN data, the script calls original0x2520 to model completion-driven scheduling of the next chunk. It does not emulate physical USB handshakes, real endpoint status transitions, SET_ADDRESS timing, SET_CONFIGURATION completion, suspend/resume, or interrupt delivery. Thus descriptor/control response recovery is verified; full enumeration on hardware is still unverified.

Control context offsets directly used by these routines:

|Offset|Observed use|
|0..7|SETUP packet|
|+8|Control transfer state byte|
|+0x10|Remaining transfer bytes|
|+0x12|Current transfer offset|
|+0x14|Maximum packet/chunk bytes|
|+0x18|Data callback pointer|

Important correction when translating the original:0x20000520 and0x20000524 are **RAM shadow state values**, not MMIO register pointers. Original0x2520 stores0x3000/0x30 there; the surrounding IRQ path later applies these values through0xf194/0xf234. They must not be treated as physical controller register addresses.

## Receive FIFO and access widths

The actual copy routine0xd4d4 takes R0=destination, R1=FIFO base, R2=length. It uses **8-bit reads** at FIFO base+i*4 and byte stores to destination+i, wrapped by original interrupt masking helpers0x2220/0x2228. TX0xf3fc instead uses32-bit stores of each byte. Preserving these widths matters when replacing MMIO access.

* EP0 OUT0x25dc calls this helper with source0x40017b00 and callback-provided destination, then updates transfer remaining/offset.
* Application vendor OUT callback0x287c reads packet count low7 bits at0x40017f2c and copies from0x40017500. This is endpoint3 RX geometry. It then invokes vendor command handling; the new C primitive deliberately stops at packet copy.
* Seven offline executions of original0xd4d4 passed at the EP0 source (length0/1/8) and vendor source (0/1/8/64). Tests seeded nonzero upper24 bits and verified that each observed read was size1 at the exact spaced addresses. These are recorded in `qmk_port/usb/control_recovery.json`.

## Concrete C components and validation

`qmk_port/usb/ranked_usb_io.h/.c` implement bounded FIFO submission, EP0 receive, vendor endpoint3 receive, and SETUP decoding using explicit `read8` and `write32` callbacks. They do not invoke vendor firmware or access hardware unless a caller provides hardware callbacks. EP0 submission is bounded to8 bytes; interrupt endpoint1..5 submission to64. Invalid arguments issue no bus writes. Callers must handle endpoint readiness, synchronization, IRQ acknowledgment, and transfer state.

Validation completed:

* Original TX machine code:18 cases (separate `usb_tx_offline_traces.json`).
* Original descriptor/control machine code:12 requests with exact responses.
* Original RX machine code:7 cases with exact byte-read addresses/widths.
* New C primitives:334 valid endpoint/length submission cases, invalid bounds, RX, and SETUP decoding via host fake-bus tests.
* New C file cross-compiled successfully using Arm GNU GCC14.3.1, `-std=c11 -Wall -Wextra -Werror -mcpu=cortex-m0 -mthumb -ffreestanding`.

Host reproduction:

```powershell
& 'C:\Strawberry\c\bin\gcc.exe' -std=c11 -Wall -Wextra -Werror qmk_port\usb\ranked_usb_io.c qmk_port\usb\test_ranked_usb_io.c -o qmk_port\usb\test_ranked_usb_io.exe
& .\qmk_port\usb\test_ranked_usb_io.exe
& .\.build-tools\bin\arm-none-eabi-gcc.exe -std=c11 -Wall -Wextra -Werror -mcpu=cortex-m0 -mthumb -ffreestanding -c qmk_port\usb\ranked_usb_io.c -o qmk_port\usb\ranked_usb_io.arm.o
```

## IRQ event decoding and scan scheduler connection

The compiler jump-table helper0x317a interprets bytes0xec18 onward as data. Decoded event0->0xec2c,1->0xecac,2->0xed46,3->0xed50,4->0xed66,6->0xed80,7->0xed9e. Event is low5 bits of0x40016000.

Event1 acknowledges value2 at0x40017eac and reaches0xed32 ->0x3078, which connects to the scan scheduler documented by the scan analysis. Its periodic/frame interpretation remains an inference; no register manual confirms the conventional SOF name. Event6 drives EP0 IN completion through0x4b20; event7 drives EP0 OUT completion through0xd474. Endpoint event acknowledgments reside in the0x40017e80 register bank, distinct from software RAM shadow states.

## Device/control engine implementation

The later implementation pass adds `qmk_port/usb/ranked_usb_device.h/.c` with actual controller initialization, SETUP processing, EP0 data/status phases, descriptor callbacks, SET_ADDRESS bookkeeping after its status stage, SET_CONFIGURATION callbacks, class request hooks for LED/report traffic, endpoint readiness, and IRQ dispatch. It has a callback interface suitable for the QMK boot-keyboard descriptor/host glue. This supersedes the earlier limitation to FIFO-only primitives.

Register operations preserve the native EP0 shared-register behavior at0x40017ed0. Valid IN is encoded0x3000 in software and maps to a masked hardware store; this value must not be written as a literal hardware register value. OUT state likewise uses0x10/0x20/0x30 software encodings. The tests caught an initially incorrect final-IN transition and now match the native descriptor status-stage stores exactly.

Native SET_ADDRESS was executed through both SETUP event0 and IN-completion event6. **The original code does not issue an address-register store.** Its verified behavior arms a zero-length IN status response with the native shared-register handshakes. The implementation repeats that behavior and updates software address only after completion. Automatic physical address application remains an inference about the controller; this has not been verified on a bus.

The auxiliary IRQ at original0xf310 tests **bit3 (0x08)** of0x40017f58 for reinitialization, when bit7 is clear. This is established by original machine-code execution, correcting a prior static bit4 interpretation. Reinitialization reproduces the controller setup and resets software configuration/address. The controller enable routine0xf0dc and delay-helper execution are platform responsibilities. `delay_original_units` receives original arguments1,1,6 without claiming that those arguments are microseconds.

`qmk_port/usb/validate_usb_device.py` compiles the new C implementation as a host fake-bus executable and compares ordered MMIO address/value pairs against original ARM execution. Passing comparisons now cover:

* SET_ADDRESS7, SET_CONFIGURATION1, SET_CONFIGURATION0, invalid address128, each with SETUP and IN-status completion:8 stages total.
* Full18-byte device descriptor: SETUP, three IN-completion events, and OUT-status completion:5 stages total.
* Entire original0x46fc controller initialization, excluding separately handled clock-enable and delay helpers.
* Original0xf310 bit3 reinitialization path, excluding clock-enable and delay helpers.

The init comparison corrected four earlier static register-address readings: the writes are to0x40017fc0,0x40017fe0,0x40017f78,0x40017f7c. The original driver analysis table and C source were corrected accordingly. Reproducible results are in `qmk_port/usb/device_validation.json`, with the descriptor trace in `descriptor_irq_comparison.json`.

Host engine checks additionally exercise descriptor chunking, configuration, software address timing, SET_REPORT OUT data/status, and transmit readiness across a completion interrupt. Cortex-M0 compilation passes `-Wall -Wextra -Werror`. The new code supplies the control-transfer functionality needed by the local runtime; no vendor binary routine is called by that runtime.

## Remaining physical validation

Offline tests model peripheral registers as supplied state and verify CPU-visible accesses. They do not establish USB electrical behavior, clock accuracy, real register side effects, physical enumeration, address application, interrupt timing, suspend/remote-wakeup behavior, or recovery after installing a new image. Unsupported power-management behavior must not be advertised by descriptors. Runtime callers serialize FIFO submission against interrupts; the local QMK runtime does this with PRIMASK. No device was opened, firmware installed, or flash erased during this work.
