# Physical QMK trial and stock recovery

The first QMK application image was written and verified on 2026-11-03,
but did not enumerate as a functioning QMK USB device. This was a failed
runtime trial, despite a correct flash readback. Warm RAM scan tests did not
validate cold application startup or physical USB timing.

After an initial unsuccessful Esc+Fn reconnect, the user tried Esc alone
at power-on. Windows PnP and hidapi both detected the original bootloader
`352d:1101`. This establishes successful recovery on that attempt; it does
not establish why the previous attempt failed or guarantee all cold starts.

The guarded stock rollback then completed successfully:

- All 117 application pages (16 through 132) were restored.
- Full 128 KiB flash readback matched the preimage overlaid with the stock body.
- Bootloader and all bytes outside the application write range were unchanged.
- The separately captured hidden 512-byte metadata block was unchanged.
- The original six HID collections with serial `rankednova` returned.
- No COMPLETE command was sent.

Machine-readable evidence is in
`live_rollback_20261103T064616_159843Z/result.json`. The failed QMK trial is in
`live_qmk_20261103T062706_170286Z/result.json`.
Both results and relevant audits are preserved in `ranked_re.db`, findings
77 through 79. Original flashed build artifacts were retained in
`qmk_port/build/flashed_20261103` before rebuilding corrected sources.

Confirmed port differences under correction are the controller's short/long
delay callback mismatch, omitted native clock calibration and startup waits,
and an emergency key check that stops at its first empty scan. Their presence
is proven by code comparison; their individual contribution to the physical
failure is not established. Corrected offline builds are not hardware validation
and must not be described as ready to flash.

The four-byte factory clock word was subsequently read through a separately
bounded read-only stub: `0x10000234 = 0x06a20060`. The original formula selects
nominal 48 MHz; this is not a physical frequency measurement. Stock returned
with all six HID collections after that probe.

Corrected source builds:

| Variant | ELF SHA-256 |
|---|---|
| Basic QMK | `102808c482f631857f157668f98efc73afa2c5901c5b973c0f4bc08dd6ccdc66` |
| QMK + VIA | `b9a2a24a88ab55638a1ebf2226c7cd815517f2136f835a1d64e53bba8817d1fb` |

They restore the native calibration sequence and startup waits, correct the
controller delay callback, retry the early held-key check within a bounded
window, and request the bootloader on detected clock/matrix/USB init failure.
The calibration implementation matches 37 native instruction fixtures plus
four callback-failure fixtures. USB delay validation includes an old-wiring
negative control. Fifteen isolated settling/readiness cases pass. The actual
rebuilt ELFs pass startup/vector checks, 17 QMK key-pipeline cases, 147 VIA
protocol/remap cases and eight USB transport cases. Full emergency-path
results (41 cases) are recorded separately in
`qmk_port/runtime/emergency_boot_validation.json`.

The prepared application flash payload and its original host SHA pins have
not been changed to these new ELFs. They are retained as evidence of the
first trial. The corrected builds are not installed; stock is the final
hardware state for this repair.

## Corrected-image physical trial

The user subsequently requested flashing the corrected VIA image. Its body
`24911be27297eef121c472f2f7e775f01f217ceb27922e0533d3ffc39a7eb969`
passed full flash and metadata readback, but QMK still failed to enumerate.
Evidence: `live_qmk_20261103T070202_026538Z/result.json`.
Esc alone held during physical reconnection again recovered `352d:1101`.
This supports successful execution through the early application key hook
on that cold start; it does not identify the later USB failure.

Stock was restored again with full readback and original six USB HID
collections confirmed. Evidence:
`live_rollback_20261103T070503_261490Z/result.json`.
Bootloader, outside-application flash and hidden metadata matched their
same-session preimages in both operations. No COMPLETE was sent.
The corrected image remains a failed physical runtime trial. Further work
should isolate USB stages with bounded RAM diagnostics rather than treating
offline protocol/MMIO traces as physical USB validation.
