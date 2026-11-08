# 02 · Update encryption

**When:** 3 November 2026 · **Status:** done for the captured update profile

The update payload is encrypted. Offline tests of direction, layout and header hypotheses
identified the transform: AES-128 forward/ECB in two passes, with a per-file key derived from
the update file header and a master key held in the bootloader. Re-encrypting the decoded data
reproduced the captured ciphertext, and the decoded code matched the independent CPU flash read
from [04](../04-firmware-dump/). The result applies to this capture and device, not to every
model or OEM variant.

Full write-up: [KEY_RECOVERY.md](KEY_RECOVERY.md).

## Contents

| Path | What it is |
|---|---|
| `offline_key_audit.py` / `.json` | Header-hypothesis search; finds the AES-forward metadata match |
| `extract_update_keys.py` | Recovers the keys and verifies the whole captured update |
| `key_extraction_result.json` | Verification result of the key recovery (key values redacted) |
| `check_vendor_key_compat.py` | Checks whether another firmware blob uses the same master-key profile |
| `drunkdeer_compatibility_result.json` | That check run against public DrunkDeer updater images (see [DRUNKDEER_COMPARISON.md](../../docs/DRUNKDEER_COMPARISON.md)) |
| `via_state.py`, `via_backup_before_zero_probe/` | Saves VIA settings around a bootloader session |

## Not included

The master key, the per-file key, the decrypted update and its intermediate files are not
published. The scripts recompute them from your own flash backup and capture
([REPRODUCING.md](../../docs/REPRODUCING.md)).
