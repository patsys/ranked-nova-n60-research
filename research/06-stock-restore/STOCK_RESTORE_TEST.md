# In-place stock plaintext restore test

> This describes the first stock rewrite. Later actual rollbacks from failed
> QMK images and a successful QMK/VIA installation are recorded in
> [the process guide](../../docs/history/REVERSE_ENGINEERING_GUIDE.md). Its timeline distinguishes
> the first identical-image rewrite from later changed-image recoveries.

The live test in `live_20261103T055849Z/result.json` completed117 stock
application pages at CPU2000..109ff, then verified the entire128KiB CPU flash
and the separate512-byte hidden metadata against the same-session pre-write
backup. Both comparisons were identical. The board returned to six original
application HID collections and zero bootloader interfaces.

Only bounded v3 was used live. It disables special metadata operations and
limits page/context/source/length, preserves the captured header, clears the
RAM transform flag, and provides guarded native protocol handoffs. No COMPLETE
command was sent. V1/v2 are historical artifacts and must not be substituted.

This is an in-place stock rewrite attempt/readback test on a working board.
It does not establish recovery from a blank/nonworking application or power
loss. Identical original/readback content does not independently measure erase
pulses or prove a physically protected controller accepted every command.
Native ACKs alone are not proof; readback is the content-verification evidence.
Vendor mode transitions can append persistent bookkeeping before/after the
same-session comparison. The QMK emergency build was not installed.

The host's --execute option performs real writes and is not a general flasher:
it pins this stock image, device identity, metadata and protocol artifacts.
Its error keepalive is read-only; indefinite recovery and power-loss safety
have not been demonstrated. Offline validations are saved beside the binaries.
