# DrunkDeer firmware comparison

Checked 5 November 2026 against public DrunkDeer firmware/updater archives and the Nova key/transform already recovered in this project. No keyboard was connected; the comparison was offline.

## Result: same master-key profile confirmed for tested packages

The Nova key from [`research/02-update-crypto/`](../research/02-update-crypto/) was tested against DrunkDeer `.enc` update blobs using the Nova header and body transform. Validation passed for:

- All 12 `.enc` files in the public [DrunkDeer Updater V2.3.4 archive](https://github.com/deerios/DrunkDeerFirmware/blob/main/DrunkdeerUpdaterV2.3.4.zip): A75 ANSI/ISO, A75 Pro, G60, G65, and G75 variants.
- The older A75 Pro v0004 image from the same public firmware collection.

For each sample, the Nova master key produced a metadata header whose declared payload size matched the blob. Both the payload-wide XOR and executable-code XOR matched, and the decrypted image began with plausible ARM vector-table values. This is strong cryptographic evidence that these DrunkDeer images use the **same master key and transform** as the tested Nova profile.

The firmware header still derives a separate file key for each image. “Same master key” does not mean all update files use the same per-file key.

The public [DrunkDeer updater reverse-engineering notes](https://github.com/svumo/DrunkDeer-Control/blob/main/docs/firmware-flash-research.md) independently report `encryption_en=1`, encrypted `.enc` images, and bootloader-side verification. Their captured A75 Pro v2.3.4 session streams the `.enc` app payload in boot mode and finalizes it with a separate command. That capture does not show a separate bootloader image write.

## Separate `DualBankBoot.bin`

The V2.3.4 public package contains `DualBankBoot.bin` under both `A75_master/` and `A75_ultra/`. Each is 8,496 bytes and both copies have SHA-256 `710ce1cb1d57f9ffc04da970f122d24d4ccc107a1f3f6871b1c0e009c80ed092`. The same folders also contain `A75Master.bin`/`A75Ultra.bin` and `blhost.exe`. The `DualBankBoot.bin` begins with a plausible ARM vector table.

This establishes that the Ultra/Master distribution includes a distinct dual-bank boot image. The public material reviewed here does **not** establish whether the official tool writes that file during a normal update, whether it is used only for factory/recovery programming, or whether it replaces the resident USB bootloader that enumerates as PID `0x1101`. The filename and neighboring `blhost.exe` suggest a separate programming path, but that is an inference, not a captured flash fact.

For the A75 Pro capture, the observed update path sent encrypted application data and a finalize packet; no separate loader image was observed. Do not generalize this capture to A75 Ultra/Master.

## Provenance and reproducibility

The checked V2.3.4 archive is the public `deerios/DrunkDeerFirmware` repository file. Its downloaded SHA-256 was `5497357ae9238cf40a1af77097d7220361ee67ba90fc048c1f2ba7d33bd05718`. The older A75 Pro v0004 package SHA-256 was `6f33e4bb0811b19db8f0d7eb5a79f216bee28c5fc28f475b78d572a096e585b1`. The compatibility checker is [`research/02-update-crypto/check_vendor_key_compat.py`](../research/02-update-crypto/check_vendor_key_compat.py); the checked aggregate results are in [`research/02-update-crypto/drunkdeer_compatibility_result.json`](../research/02-update-crypto/drunkdeer_compatibility_result.json).

The checked archives are not duplicated in this repository. Supply an extracted `.enc` and the local Nova key file to the checker. It prints validation metadata and checksums, not the key or plaintext image.
