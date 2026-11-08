# Safety, provenance, and inclusion notes

## Device and evidence

Research was conducted on a user-owned Ranked Nova N60 and captured vendor updater traffic. Analyses, measurement logs, small extracted blocks and controller logs are kept next to the scripts in the phase folders under `research/`. Vendor firmware images, the firmware update capture, decrypted firmware, full disassembly listings and key material are not included; the evidence manifest records byte length and SHA-256 for every file, with `"included": false` for those. Capture timestamps and machine-specific paths may reflect the original Windows host.

## Hardware safety boundaries used

- Diagnostic bootloader stubs were built without flash erase/program calls and were used for RAM-only inspection and bounded USB reads.
- Firmware programming used a bounded application-only flasher with pre/post readback and checks for protected bootloader, out-of-range flash, and hidden metadata.
- The final persistence check was read-only: it took two full flash snapshots and did not send erase/program commands.
- No reset/format command was used to clear VIA or other storage during the investigation.
- The experimental persistence backend is not accepted. Do not use it as general NVM until raw address behavior is understood.

## Credentials and excluded data

- The SQLite database (`ranked_re.db`) is intentionally excluded, as requested.
- The GitHub token file and all authentication material are excluded.
- Python virtual environments, build object files, ELF/map output, and redundant generated build trees are omitted. Source and validation evidence are kept.

## Licensing

The flasher component retains its own license file. QMK-derived and platform source files retain upstream/component license headers. Vendor firmware and capture material is proprietary and therefore not included; the remaining small excerpts serve to document the research and do not grant redistribution rights. Before changing this repository to public visibility, review component licenses and the vendor-material terms.

## Second board (7 November)

The v1.0.7 bootloader, stock application, info-flash and RAM dumps read from the second
Nova N60 are deliberately **not** included; `research/08-bootloader-v107/results/register_snapshot_v107.json`
records their size and SHA-256. Included are measurement logs, flasher/diagnostic run
results and peripheral register values. All writes on that board went to scratch page
0xA0 (diagnostics) or the application pages (flasher), each followed by a whole-flash
and info-flash comparison.
