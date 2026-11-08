# Independent stock restore host review

Later integration note: actual execution used v3, not v1/v2. Native error and
timeout paths can exit an update; merely closing HID does NOT guarantee staying
in boot mode. V3 redirects the first native return to the USB menu, and the
host has a read-only keepalive on failure. Power-loss/independent recovery is
unverified. The later live in-place test succeeded without taking the error
path; see `live_20261103T055849Z/result.json`. Earlier review text below records
the pre-v3 design and must not override these limitations.

Review is offline only. No device opened and no erase/program operation performed by the reviewer. Reviewed `restore_stock.py` plus its `BlockReader`, `Channel`, boot-open and metadata-read dependencies.

## Execution gate

**The original v1 stub/protocol combination is not ready for live execution.** The existing native protocol test proves that after117 DATA pages, the next reader START is rejected while the outer DATA-active state remains set. The v2 stub must have its own successful original-native117-DATA-to-reader-START proof before its hash is accepted by the host. Updating a hash alone is insufficient. The host should machine-check the successful protocol artifact and its exact stub/body hashes before any device writes.

The reviewer has not approved an untested v2 transition or physical flash-controller behavior. This review addresses host containment and failure handling.

## Findings sent to the primary agent

1. **Wrong-device ambiguity:** `open_bootloader(True)` opens an already-present bootloader before attempting to switch the intended application. Merely checking one running application does not prevent that. The host was updated during review to require zero pre-existing boot interfaces, then zero application collections and exactly one boot interface after the transition. Keep both checks.
2. **Integrity checks must remain active:** the script uses assertions for safety gates. An explicit refusal under Python optimization (`if not __debug__`) was added during review. This prevents `-O` or `PYTHONOPTIMIZE` from removing the gates.
3. **Pin the reference and original START header:** in addition to the fixed body, stub and metadata hashes, check original reference SHA-256 `5adca278d90a0672e05dfe5ad47d1635242f9ec0ff78827d83d9f28d6ccd8b49` and native START first52-byte SHA-256 `3a555131918325b6d55eef48d7b2299ab872bfa1b6caa4659458db6ced1a2fc5`. Only checking header byte6 and the clear length does not bind the complete captured encrypted header/addressing context. An accidental changed capture must fail before DATA, not after readback detects a shifted/corrupt write.
4. **Final identity:** require six application collections **and zero boot interfaces** before reporting success. The existing final assertion checked the application count alone when first reviewed.

## Failure and cleanup behavior

The host sets `write_started=True` and saves it **before** sending any part of the first DATA frame. A partial HID write, DATA timeout, bad reply/status, readback failure, hidden-metadata mismatch or later log-write failure therefore cannot take the normal `reader.close()` application-return path while `verified` remains false. It closes only the host handle and records that the device was left in bootloader. This is the correct conservative boundary; closing the host handle itself is not a firmware jump.

Before any DATA, cleanup may return to the application because the bounded START and read-only probes do not intentionally modify firmware. After DATA, application-return cleanup is permitted only once the **whole128KiB flash snapshot equals the same-session prewrite snapshot and the512-byte hidden information block equals its same-session prewrite copy**. Native ACK/status4 alone never sets `verified=True`.

The same-session comparison avoids silently ignoring vendor bookkeeping changes. It is deliberately stricter than comparing the rewritten application pages alone. A mismatch outside the application, including the vendor settings/journal area, is a failure that leaves bootloader active. The original prewrite snapshot and metadata are saved before destructive operations.

`write_started` is conservative if the log save fails before the first DATA: the script can leave the device in bootloader despite no write having happened. This is safe, though the user may need a later explicit recovery/cleanup step. `KeyboardInterrupt` still reaches the `finally` containment path even though the exception logger catches `Exception` rather than `BaseException`.

## Scope preservation

The fixed117-page body is59904 bytes covering CPU `0x2000..0x109ff`. The host checks that these exact bytes already match the running stock image before rewriting them, and that current boot/application bytes through `0x19fff` match the stock reference. Pages below16, above132, vendor-data pages from `0x1a000`, and the separate information block are outside the bounded programmer range. The host sends no COMPLETE command; metadata is read before/after rather than rewritten.

Physical containment ultimately depends on the separately audited bounded stub, its native ABI/context guards, actual controller semantics, and the v2 post-transfer transition. Those requirements cannot be established solely by this Python review.
