# 05 · Plaintext DATA bypass (RAM only)

**When:** 3 November 2026 · **Status:** done

A known plaintext page was sent as DATA with two RAM settings of the bootloader's crypto flag,
while own stubs replaced the erase/program step with an echo. With the flag cleared, all 512
bytes arrived unchanged; with it set, they were transformed. This proved that the bootloader
decrypts DATA before programming and that plaintext can be passed through, without writing flash.
A whole-flash comparison afterwards confirmed nothing changed.

Full write-up: [PLAINTEXT_BYPASS.md](PLAINTEXT_BYPASS.md).

## Contents

| Path | What it is |
|---|---|
| `stubs/` | The two echo stubs (crypto flag 0 and 1), source and builds |
| `scripts/build_ram_bypass.py` | Builds the stubs |
| `scripts/test_plaintext_bypass_live.py` | The live test |
| `scripts/verify_flash_after_bypass.py` | Whole-flash comparison after the test |
| `result.json`, `result_attempt1.json` | Results of the final and the first (failed) attempt |
| `ordinary_read_control.json`, `observed_source_crypto_1.bin`, `ordinary_control_data_region.bin` | Control run without the bypass |
| `flash_verification_usb.json` | USB log of the post-test flash read |

## Not included

The plaintext test page (the first page of the stock application) and the post-test flash image
are vendor firmware and are not published.
