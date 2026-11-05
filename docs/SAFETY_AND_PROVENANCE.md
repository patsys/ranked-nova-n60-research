# Safety, provenance, and inclusion notes

## Device and evidence

Research was conducted on a user-owned Ranked Nova N60 and captured vendor updater traffic. Firmware dumps, packet captures, extracted blocks, and controller logs are retained as evidence under `evidence/`. The evidence manifest records byte length and SHA-256 for copied files. Capture timestamps and machine-specific paths may reflect the original Windows host.

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

The flasher component retains its own license file. QMK-derived and platform source files retain upstream/component license headers. Some vendor firmware/capture evidence may be proprietary; inclusion is for documenting the research and does not grant redistribution rights. Before changing this repository to public visibility, review component licenses and the vendor-material terms.
