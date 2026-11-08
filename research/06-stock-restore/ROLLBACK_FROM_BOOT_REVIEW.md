# Stock rollback from an already-present bootloader

The current `restore_stock.py` is an in-place stock rewrite tool. Its preconditions require six original application collections, no existing bootloader, and the complete current application/code area to equal stock. Those are deliberate constraints of that task and will reject a QMK or partially written application. Removing only the application-equality assertion would not produce a complete rollback tool.

This review does not execute a rollback or supply proof of independent recovery after a broken application. No device was accessed.

## Required existing boot state and identity

An already-enumerated boot interface must be opened directly, without expecting or sending the original application command. Require one exact0x352d:0x1101 vendor interface and bind subsequent reconnects to the same observed device path/identity. Preserve boot descriptor/serial/path evidence. The GETV words must match the known boot profile (`a1050000`,`a1040000`), but VID/PID/version alone are insufficient identification.

Before writing, obtain and compare all8192 boot bytes against SHA256 `e46c6d9300a13f4d2eea7c16584d24ea6e4e1b83815e5f84f389d4aeb0915f62`. This establishes the exact native ABI required by the bounded guards and stack offsets. Read the separately captured metadata block and require its expected hash `3bce58cb1e15aa6adfb8120c12b6911466a8d1f611a3efeefcb72c6bd7ca4d49`, unless a separately reviewed known configuration replaces that baseline.

Important protocol state: GETV or START during an active ordinary DATA session can NACK and return toward reset. Direct boot discovery does not prove that session is inactive. Use a known fresh boot entry or a confirmed read-only holder state; do not assume an arbitrary existing updater session can be probed without changing control flow. The V3 saved-return patch provides one USB-bootstrap reentry after failure, and the host holder must renew protection. It does not survive power loss.

## Fixed rollback assets and host checks

* Captured START first52-byte hash: `3a555131918325b6d55eef48d7b2299ab872bfa1b6caa4659458db6ced1a2fc5`; require mode1 and clear length0x1cc00. Do not invent a new encrypted header.
* Prepared stock body:59904 bytes,117 full pages, CPU0x2000..0x109ff, SHA256 `7f7f5853e7192c737be85cc00e0b21db56e8a40bd68495900002921ef914762c`.
* V3 bounded stub:440 bytes, SHA256 `e4c466571f03c5ece7ae4417c281dd9be3787d659945633acec7cfb92dae3a8c`; allowed pages16..132, exact512-byte packet/context/source guards, special metadata operations disabled.
* Release stub SHA256 `57332cb094949feeba32c44fa829bb57069eaef61d92bceab161601737af4323`; release only after stock readback/preserved-region verification. Then GETV directly, with no intervening normal START.
* Holder stub SHA256 `1c04bf5c4c9ae72885acfd8a62dc948219bb36c4cbc7a12ea3106367a0ebf871`; this is a host-serviced RAM hold, not a power-independent recovery mechanism.

Require the matching offline guard/protocol/failure/release validation records and Python assertions enabled. The stock body and writer assets must be immutable/hash-bound for that run. Reconnect logic must not silently choose a different keyboard.

## Comparisons that differ from the in-place rewrite

Back up the full current128KiB and hidden512-byte metadata before any mutation. Allow application bytes0x2000..0x109ff to differ from stock, since replacing those bytes is the rollback's purpose. Require the boot block to match the known bootloader. Preserve the session's original bytes outside the exact rollback range, including settings/journal data and hidden metadata; do not require those regions to equal a stale historical backup when normal mode transitions can append bookkeeping.

After writing, verify:

```text
after[0x2000:0x10a00] == fixed_stock_body
after[:0x2000] == before[:0x2000]
after[0x10a00:] == before[0x10a00:]
after_hidden_metadata == before_hidden_metadata
```

The current in-place assertion `after == before` must therefore be replaced by these exact comparisons in a dedicated rollback implementation. Full equality is expected only when the before-image was already stock.

If the preceding QMK installation modified any bytes beyond0x10a00, restoring only117 stock pages does not restore those extra modified pages. Check the actual installation manifest and dirty-page set. Either prove all dirty pages are within16..132 or prepare a separately bounded, validated restore covering the complete changed range. Do not silently broaden the existing stub guard or overwrite persistent settings to clear leftover code.

## Interrupt and recovery limits

The same boot/application-vector dependency applies to rollback from QMK: stock vector-first can point into handlers not restored yet, and vectors-last can leave QMK vectors pointing into overwritten QMK handlers. See `firmware_dump/boot_irq_dependency_audit.md`. A rollback writer must maintain the validated interrupt/polling conditions across the transfer, not merely inherit an unexamined application interrupt state.

If QMK cannot request boot mode and the device does not already expose the known bootloader, this host-side rollback route is unavailable. The current captured metadata disables the bootloader's optional GPIO recovery configuration, and its enabled patch-list path skips application checksum rejection. There is no demonstrated automatic fallback after a broken application. An actual independent recovery entry remains unproved; this review must not be represented as a guarantee that any failed flash can be undone.
