# Recovery recheck after QMK USB enumeration failure

Scope: offline source/binary review after the verified application write, failed QMK enumeration, and unsuccessful reported held-key reconnect. No hardware commands or additional flash writes were performed by this audit. The original bootloader and captured metadata remain the evidence base; a missing USB interface does not establish that either was erased.

## Complete known native entry conditions

|Native path|Result|Reachability from the current physical keyboard state|
|---|---|---|
|Reset0x1cc ->startup0xd8 ->scatter0x150 ->main0x700|Normal boot selection|Runs on a true core reset; a USB bus reset alone is not proof of that reset|
|Clock readback mismatch0x722..0x738|Calls reset primitive0x24c; no USB mode selection in that branch|Not a usable or controllable recovery selector established here|
|Retained request0x4001400c matches configured/default value at0x77c..0x7a6|Mode2, clears request, USB bootstrap0x848|Software/debug execution must write the request before SYSRESETREQ; known value0x5ac396c5|
|Metadata0x10000714 notFF|Overrides the default request value|Actual valueFF, so no different secret request is configured|
|Enabled patch list0x7a8..0x7e0 has invalid target|Selects USB mode|Actual targets0x400130e8/ec are valid; no physical key modifies this list|
|Patch list absent, configured GPIO pair both low0x7e2..0x7fc|Selects USB mode|Not reached with this actual valid patch list; GPIO selector0x10000700 is alsoFF/disabled|
|Patch list absent, application/metadata validity checks0x7fe..0x83a fail|Selects a USB error mode|Bypassed by this actual patch list; not a fallback on the installed QMK body|
|Mode low16 equals2 at0x83c..0x848|USB bootstrap|Depends on an earlier selector above|
|Normal patch branch0x892..0x8b4, then0x8b6..0x8c0|Reads application reset vector0x2004 and BLX to it|Invalid/erased vector is not checked there and does not itself select USB recovery|
|Boot exception0x1de ->0x3ac|Branches through application vector indexed by IPSR|No boot-owned HardFault fallback; malformed application exception handling can remain stuck|
|Native updater error/timeout return to0x87e|Clears request and calls0x24c on ordinary return values|Normally resets toward application; temporary V3 RAM saved-return changes are lost on a new core reset|

No separate reset-reason, watchdog-reset, USB-reset, or malformed-application-vector condition selecting boot USB was found in the extracted reset/main path. This is a statement about reviewed code, not proof that silicon ROM lacks another strap/debug mode.

The actual metadata also configures clock overrides at0x10000718=0,0x1000071c=0x0100b1b1,0x10000720=2. These are applied during ordinary clock setup; they are not an additional documented physical recovery selector. The boot control branch still follows the valid patch-list path described above.

## Held keys: application hook, not native physical boot selection

The flashed runtime checks `nova_emergency_boot_requested()` after clock/matrix initialization and before USB initialization. That hook can write the retained request and request a core reset if its analog input condition is recognized. It cannot run if reset/vector/startup or an earlier initializer fails.

More specifically, `emergency_boot.c` returnsfalse as soon as the **first scan** has no held position. Three required scans are not a warmup period or a retry window. Cold ADC/external sensor settling can therefore prevent this hook from recognizing keys. The successful live Esc RAM test ran while stock firmware/boot had already powered and initialized the analog hardware; it did not prove cold-power recovery behavior. Its active report did show nonzero samples and row0 bit0 when Esc was held, so the physical sensor can be read in that warm condition.

A true core reset while sensor power remains present could rerun the hook in a different settling condition. No verified way to trigger that reset is currently available through the failed USB interface, and no identified physical reset control/pin is supplied by the evidence. USB bus re-enumeration or a host port reset must not be described as an ARM core reset. Unknown pads, power/clock glitches, or assumed BOOT straps are not recommended.

The hook is checked only at application startup. Holding keys later while the application remains running does not re-execute it. The native bootloader's optional GPIO selection is disabled independently of the QMK hook, so adding more stock key combinations does not create a proven native recovery path.

## Concrete QMK USB timing discrepancy

Native controller initialization0x46fc calls0xeea8/0xeed4, which use **long** helper0xdd80 for arguments1,1,6. In the flashed runtime, `usb_keyboard.c` wires the controller's delay callback to `nova_platform_delay_original_units`, corresponding to short helper0xdde8. `nova_platform_delay_original_long(10)` is called before controller initialization, but that does not replace the missing per-step long delays.

The long helper performs an initial count<<7 loop and count additional loops with999; the short helper runs only count iterations of the raw loop. This is a concrete implementation mismatch that can affect reset/pull-up timing. It is not proof that this mismatch alone caused the failed descriptor request, and source edits cannot repair the already flashed image without regaining a programming path. Earlier differential MMIO tests explicitly skipped delay helpers, so they did not validate this timing equivalence.

SET_ADDRESS handling remains based on native application trace equivalence: the native path did not issue a software address-register store in the tested code, and the replacement repeats those status handshakes. Physical automatic address behavior, actual reset events and peripheral side effects were never established by the offline trace model. No new fact here converts that assumption into a hardware guarantee.

## Endpoint0 recovery-command possibility and Windows limits

The custom QMK control callback accepts interface1 HID SET_REPORT for a32-byte output report even before a configured flag is checked, and its main loop can process the queued VIA command. Thus a functioning, accessible EP0 control pipe could in principle carry a software boot request without working interrupt HID traffic. That is conditional on actual USB transaction delivery and the main loop continuing; neither follows from Windows VID0000/PID0002 descriptor-failure status.

Microsoft documents `WinUsb_ControlTransfer` with a valid interface handle associated with the selected configuration, and WinUSB requires its function driver/interface to be available. The hub-level descriptor IOCTL retrieves descriptors, not arbitrary HID OUT requests. Microsoft explicitly marks the old raw USBUSER operations, including OPEN_RAW_DEVICE and SEND_ONE_PACKET, as “Do not use.” No documented reliable existing user-mode path was found to inject this class request into the current failed-enumeration device. No blind control transfer, driver replacement, or raw-host-controller request was attempted.

Primary references:

* [WinUsb_ControlTransfer](https://learn.microsoft.com/en-us/windows/win32/api/winusb/nf-winusb-winusb_controltransfer)
* [Windows desktop app and WinUSB function-driver requirements](https://learn.microsoft.com/en-us/windows-hardware/drivers/usbcon/windows-desktop-app-for-a-usb-device)
* [Hub descriptor retrieval IOCTL](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/usbioctl/ni-usbioctl-ioctl_usb_get_descriptor_from_node_connection)
* [USBUSER request restrictions](https://learn.microsoft.com/en-us/windows/win32/api/usbuser/ni-usbuser-ioctl_usb_user_request)

## Current restoration boundary

The prepared stock rollback remains usable only after the known bootloader interface or another verified execution/programming channel is recovered. VID/PID0000:0002 is not that interface. MCU manufacturer/part and any silicon ROM ISP entry remain unidentified. Physical board inspection for actual chip markings and clearly labeled reset/debug controls could supply new evidence; the existing binary does not justify naming pins or shorting pads.

The stock backup, separate metadata capture, verified readback and preserved boot block provide restoration data. They do not by themselves provide access to a currently unavailable boot interface. No additional software-only recovery route has been proved by this recheck.
