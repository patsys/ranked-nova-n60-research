# Plaintext DATA bypass without installation — verified

The known 512-byte plaintext application page, starting `50 1c 00 20 11 22
00 00`, was sent with two RAM configurations. Uploaded erase/program entries
were replaced with no-ops or diagnostic USB echo. No original flash programmer,
flash-controller access, or COMPLETE was used by the own payload.

| Trial | Flag at 0x20000214 | Source pointer | Observation |
| --- | ---: | --- | --- |
| Control | 1 | 0x20000554 | Transformed bytes differ from input |
| Bypass | 0 | 0x2000032c | All 512 bytes match plaintext exactly |

Packet context was 0x20000324; bypass source therefore equals context+8,
the raw DATA buffer. The initialization entry verified LR 0x1021 and saved
LR 0xcc3 before changing the RAM flag. The diagnostic programming entry
returned source slices and metadata over USB, preserving the native packet
length and registers. Fifty offline cases checked both alias layouts, all
slice/metadata sequences, and guard failures. Writes were bounded to the RAM
flag, stack and native reply buffer. Native USB callbacks were mocked only
offline; physical USB replies verified the actual returned data.

Plaintext and bypass-source SHA256:
`814535da3efb45c2d5c225da304875e3de8a887b31ff916cd04a10bb5710c026`.
Crypto-enabled source SHA256:
`cd6333dcb9c3aa2b902876b42a21e77491c596c9ff738624274b583628fe3750`.

This proves plaintext delivery to the programming entry in RAM, not successful
installation, boot-time acceptance, QMK compatibility or recovery writing.
A valid captured vendor START header was still used. This is a DATA-transform
bypass, not proof that every header/authentication step has been bypassed.

## Flash verification qualification

The post-test 128 KiB read had an identical bootloader and application
code/erased region at 0x00000000–0x00019fff. Only 32 bytes differed from the
older backup: four identical `01 00 05 09 00 00 0f 5a` records appended at
0x1a2e8–0x1a307 to an existing sequence of such records. Thus **whole-flash
hashes did not match**; do not describe every flash byte as unchanged.

A separate ordinary read session, with no DATA and no crypto-flag change,
appended one more identical record at 0x1a308–0x1a30f. This is consistent with
vendor mode-transition/bookkeeping behavior independent of firmware
installation. Its precise writer/trigger is not isolated. No firmware code
was installed or changed; normal mode transitions can update persistent data.
Sessions ended in application mode with six HID collections and no bootloader.

## Evidence

`result.json` contains control/bypass captures and post-test comparison.
`observed_source_crypto_0.bin` (not included: it is the first page of the stock
application) is the exact returned plaintext page;
`observed_source_crypto_1.bin` is the control result. `flash_verification_usb.json`
contains the post-test read; the resulting flash image `flash_after.bin` is not
included (its SHA-256 is in `evidence/MANIFEST.json`).
`ordinary_read_control.json` documents the independent no-DATA control.

`result_attempt1.json` records an initial successful custom echo followed by
the host incorrectly waiting for a second ordinary ACK. The corrected host
accepts the custom echo as the reply. The additional normal ACK is optional.

Tools: `../build_ram_bypass.py`, `../test_plaintext_bypass_live.py`, and
`../verify_flash_after_bypass.py`. The last tool deliberately reports failure
when the entire old snapshot differs; its failure is retained as evidence,
not silently converted into a successful whole-flash comparison.

The earlier ZIP remains a pre-bypass bundle. Updated SQLite findings and this
directory contain this later experiment and its qualification.
