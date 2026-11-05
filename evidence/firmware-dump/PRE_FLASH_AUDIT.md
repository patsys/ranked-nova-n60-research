# Pre-flash audit using extracted bootloader and live information block

No erase, firmware programming, DATA or COMPLETE operation was sent to the
keyboard during this audit. The only new hardware operation was a bounded
RAM payload reading the512-byte information block that the bootloader itself
reads at10000600..100007ff. Sessions returned to six normal application HID
collections and no bootloader interface. Vendor mode transitions may append
bookkeeping records as already observed; whole-flash immutability is not claimed.

## Results

1. The prior128KiB extraction did not include this separate information region.
   Its live capture has a valid metadata XOR, tag1, original app lengthE908,
   and expected application XOR25a4f084. That XOR exactly matches the original
   CPU-visible bytes at2000..10907.
2. This device enables a register-patch startup path. It validates and writes
   400130e8=ffff0000 and400130ec=ffffffff, then jumps through application reset
   vector2004. That path skips the available metadata/application XOR checks.
   Both QMK images reach the application-call instruction offline with the
   actual captured information block. This is boot-selection evidence, not
   successful physical execution.
3. Erased/invalid application vectors also reach an attempted call on that
   path. An invalid application does not automatically select USB recovery.
4. The configurable physical recovery-pin word isFFFFFFFF(disabled). A retained
   request magic5ac396c5 still selects USB bootstrap before the application is
   read. The original application's3ed8 routine sets that request and writes
   AIRCR to reset. This depends on an executing application/debug path; a
   separate recovery route for a broken application has not been demonstrated.
5. The captured updater uses mode1 with application base2000. Another native
   mode selects base0. The vendor stub does not reject boot pages0..15. An
   offline stub-boundary test issues erase/program controller commands there,
   and rejects pages256/up. Mode/address reachability does not establish that
   physical hardware would permit those writes; protection semantics remain
   unverified. The e8/ec startup settings alone are not proof of boot protection.

## Evidence

- boot_safety_audit/metadata_10000600.bin andmetadata_read_result.json: actual
  live information block and USB transaction evidence.
- boot_acceptance_audit.md / boot_acceptance_validation.json: original boot
  startup, normal-path fixtures, actual metadata with original/QMK/corrupt images.
- recovery_entry_audit.md / recovery_entry_validation.json: exact-config recovery
  gating, disabled GPIO path, retained request, invalid application fixtures.
- boot_safety_audit/stub_page_boundaries.json:16 actual vendor-stub boundary
  calls in a modeled controller, native ABI helpers and RAM guards.
- flash_bounds_audit.md / flash_bounds_audit.json: native START/DATA address
  routing, validity checks and explicit cryptographic/controller assumptions.

## What this changes

The bootloader's current startup path is compatible with selecting the QMK
reset vector; a compulsory signature/checksum rejection was not found on that
path. Conversely, a preserved bootloader does not by itself guarantee recovery
from a failed app. The current research QMK bootloader/reset functions stop
execution rather than invoke the recovered original boot-request/reset path.
Those must be addressed before relying on software re-entry.

The remaining practical gaps are an application-independent recovery route,
physical USB/analog/timing validation, and an application-bounded writer plus a
verified restore procedure. These findings do not authorize or perform flashing.
