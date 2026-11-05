# Prepared QMK image review

## Corrected second trial (2026-11-03)

The current prepared body is `24911be27297eef121c472f2f7e775f01f217ceb27922e0533d3ffc39a7eb969`,
from corrected VIA ELF `b9a2a24a88ab55638a1ebf2226c7cd815517f2136f835a1d64e53bba8817d1fb`.
It retains the same 117 application pages and fixed stock rollback body.
File-backed ELF loads now end at `0x5914`; data is60 bytes, variable BSS1656,
stacks512+1024 and remaining heap3992 bytes.

This build adds the recovered factory-word clock calibration, original long
startup waits100/300, correct long USB delays1/1/6, bounded early-key retries,
and bootloader requests on recognized initialization failures. Source hashes,
linked test hashes and the original boot-selection simulation are bound in
the updated manifest. The exact body passed the native117-page transfer,
readback-reader transition and release model with interrupts masked.

Prior physical released/Esc+Fn RAM observations are preserved unchanged.
`ram_scan/inherited_observations_proof.json` compares the actual RAM-payload,
old-image and corrected-image acquisition code in eight modeled cases.
It establishes component equivalence only, explicitly excluding added settling
delays and any claim of physically tested corrected cold startup. This first
physical flash of the corrected image was explicitly requested by the user.
The host validates that proof's fixed SHA and the original trial artifact hashes.

First-trial preparation files and image are preserved in `first_trial_artifacts`.
The following original review describes that first trial, not the current body.

## Historical first trial

Preparation performed no device access. `prepare_image.py` has no HID or transport dependency and produces only local artifacts.

The image is a fixed117-page application body, CPU addresses `0x2000..0x109ff`, SHA-256 `071ee8e608a2332b6462a12191260572319706cbc67a96df2d405276848a92ef`. Its source is the validated emergency-enabled VIA ELF `11b02d44086d3b658b3479ae64145d58b56f71ebe04a15fceee8c041622782fb` overlaid on the independently pinned stock body. It contains no bytes for the bootloader below `0x2000`, settings from `0x1a000`, or hidden information region at `0x10000600`.

ELF flash payloads end at `0x576c`. All old stock bytes not covered by ELF file-backed PT_LOAD segments remain untouched, including the entire tail `0x576c..0x109ff`. Initialized RAM data is sourced from its legitimate flash load address; RAM-only stack, BSS and heap reservation segments contribute no file bytes. The fixed preparation rejects unexpected source hashes, changed build/source/config/test artifacts, out-of-range loads, overlapping flash payloads and invalid vectors.

The separate rollback body remains the original117-page stock application, SHA-256 `7f7f5853e7192c737be85cc00e0b21db56e8a40bd68495900002921ef914762c`. Its availability and the completed stock rewrite do not demonstrate recovery from an application that can no longer run.

The original extracted reset/startup/main was executed against the prepared image and the actual captured information block. It reached QMK reset at `0x2170`. The only flash-controller-neighborhood writes in this emulator path were the captured boot patches to `0x400130e8=0xffff0000` and `0x400130ec=0xffffffff`; no erase/program command was executed. This is a control-flow test with modeled MMIO and bypassed original delay, not physical boot validation.

Physical runtime remains unverified. In particular:

- Nominal clock, USB hardware, analog calibration and physical sampling timing have not been demonstrated with QMK on the keyboard.
- Default any-key emergency entry uses recovered raw thresholds. Resting values above30 could falsely select bootloader. That failure would ordinarily leave the bootloader accessible if the early hook successfully executes.
- A failure before application reset/startup/clock/matrix initialization reaches the emergency hook cannot be recovered by that hook. The captured metadata disables the original configured hardware pin-pair override (`0xffffffff`) and selects patch-list mode, which does not guarantee checksum-based fallback. Recovery from a fully nonworking application is therefore not proven.
- Allocations fit the conservative original-used lower RAM window:40 initialized bytes,1656 variable BSS bytes,512-byte exception stack and1024-byte process stack, with4016 bytes left as heap. Offline observed stack use is not a physical worst-case guarantee.
- VIA edits use RAM-only storage and disappear on reset or power loss.

`manifest.json` binds the prepared body, rollback body, source ELF, build/source/configuration hashes and current validation evidence. It intentionally reports `physical_runtime_validated=false`.
