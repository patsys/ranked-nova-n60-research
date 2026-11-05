# Reproducing the research

## Offline first

The repository contains analysis tools and recorded evidence. Start with offline checks; they do not contact a keyboard.

- Capture/update framing: `programs/analysis/analyze_upload_capture.py` and `programs/analysis/analyze_firmware_dump.py`.
- Crypto validation: `programs/crypto/offline_key_audit.py` and `programs/crypto/extract_update_keys.py` (requires the included capture/profile inputs and cryptography backend).
- Stub construction and emulation checks: see scripts and README files under `programs/read-only-stubs/` and `programs/ram-bypass/`.
- Flasher unit tests: from `programs/flasher/`, install dependencies from `pyproject.toml` in a clean virtual environment, then run `python -m pytest`.
- QMK source: build using the QMK CLI version and toolchain documented by the copied QMK/platform notes. The upstream QMK checkout is intentionally not vendored; obtain QMK separately and apply the Nova platform/user sources.

## Hardware tests

Hardware scripts are clearly named and retained with their original validation reports. Inspect a script before running it: some are read-only probes, while `programs/flasher/` and `programs/stock-restore/` contain write-capable update/rollback commands. The final NVM persistence path is not accepted. Do not run any persistence write against a device until the address discrepancy in `docs/STATUS.md` is resolved.

The checked-in validation reports identify which results are offline, emulated, or physically confirmed. A passing offline build or image check is not a physical runtime test.
