# Current status — 5 November 2026

## Working on the tested board

- Research QMK image boots and enumerates after the corrected startup/USB work.
- Normal Neo2 typing works, including the keys that initially missed events.
- RGB works, including solid colors and moving rainbow. Z's weak blue channel also appears with stock firmware and is treated as a likely hardware LED defect.
- Eight-key chord test passed after the NKRO endpoint correction.
- Windows key-wake from sleep worked on the test host.
- QMK CLI build, offline flash-image validation, bounded flasher, and full application readback verification were exercised.

## Not working or not ready

- Persistent VIA is **not verified**. The last read-only probe was stable, but the remap slot returned `0x0001` after reset. Diagnostic address `0x1F744` remained erased; changed bytes were observed at `0x1F408..0x1F40C`.
- The custom NVM backend is experimental and cannot be submitted as a reliable feature.
- Exact processor ordering code remains unidentified.
- Upstream packaging/contribution checks, independent clean setup reproduction, and broader hardware/host validation remain.
- No QMK PR has been created.

## Recommended next steps

1. Analyze QMK wear-leveling append/consolidation addresses and flash-controller address encoding offline. Map each expected logical write to controller register value and CPU-view byte offset.
2. Add a host-side flash simulator test for each encoding hypothesis; do not send another hardware write until raw address and diagnostic verification agree.
3. If a safe corrected model is established, test on a disposable emulated flash image first, then plan one bounded hardware test with fresh full-flash backup and readback.
4. Once persistence passes independent cold-power and raw-flash verification, remove temporary diagnostic HID code and rerun standard QMK build/lint/flash checks.
5. Finish contribution packaging and licensing review. Only then consider opening a PR.

## Latest read-only probe

`evidence/experiment-results/final-read-only-probe/result.json` reports `probe_only=true`, `write_started=false`, stable before/after snapshots, and unchanged bootloader, outside-application bytes, and hidden metadata. The follow-up read-only VIA GET_KEYCODE result is in `evidence/validation/via_persistence_replug_check_20261104.json` and the updated audit.
