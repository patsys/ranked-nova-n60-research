# 01 · Update capture and USB protocol

**When:** 2 November 2026 · **Status:** done

The official Ranked updater was captured with USBPcap while it updated the keyboard. Parsing
that capture mapped the bootloader protocol (GETV / START / DATA / COMPLETE framing) and showed
that every START packet carries a small 440-byte Thumb stub that the bootloader runs from RAM.
That stub became the entry point for all later device-side work.

## Contents

| Path | What it is |
|---|---|
| `scripts/analyze_upload_capture.py` | Packet chronology of the update from `fw_update.pcap` |
| `scripts/extract_vendor_stub.py` | Extracts the plaintext START stub (`vendor_stub.bin`) from the capture |
| `scripts/audit_vendor_stub_pages.py` | Offline address-boundary audit of the vendor stub |
| `captures/upload_capture_chronology.json` | Packet chronology produced by the first script |
| `captures/communication_final_state.json` | USB state after the first communication tests |
| `captures/firmware_diff.html` | Comparison page from the first analysis |

## Not included

`fw_update.pcap`, `layout_cap.pcap` and `vendor_stub.bin` contain vendor firmware and are not
published. Record your own capture as described in
[REPRODUCING.md §1](../../docs/REPRODUCING.md); `evidence/MANIFEST.json` lists the SHA-256 values
of the files used here.

## Next

[02 · Update crypto](../02-update-crypto/) decodes the update payload,
[03 · Bootloader stubs](../03-bootloader-stubs/) uses the START stub slot to run own code.
