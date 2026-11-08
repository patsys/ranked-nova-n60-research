# Recovered update keys and verified AES transform

## Result

The captured Ranked Nova update can now be transformed completely offline.
No keyboard reboot, bootloader session, erase or firmware write was needed.

The key values are not published. `extract_update_keys.py` recovers them from your own
flash backup and update capture (see `docs/REPRODUCING.md`).

| Material | Hex | Source |
|---|---|---|
| AES-128 master key for this recovered profile | `<redacted-master-key>` | Original bootloader flash`0x173c..0x174b`, initialized RAM`0x2000021c` |
| Per-file key for `fw_update.pcap` | `<redacted-file-key>` | AES-forward transform of the second16-byte file-header block |

The native function`0x398` copies the master key into the crypto descriptor's
first16-byte buffer at`0x200007c0`. Actual reset/scatter execution reproduces
the RAM constant, and native`0x398`/memcpy execution verifies the copy.
The MCU-specific primitive at`0x29c` corresponds to standard AES-128's
**forward/encrypt** operation for the recovered update transformation.

## Exact file transform

Let `E(K, X)` mean AES-128 ECB encryption of16-byte-aligned `X`, with byte
ordering exactly as written in the files. No word swaps or transpose are used.
For the32-byte update-file header `H` and ciphertext body `C`:

```text
metadata = E(master_key, H[0:16])
file_key = E(master_key, H[16:32])
plaintext = E(file_key, E(master_key, C))
```

In the captured START frame, `H` occupies offsets16..47. Native START first
transforms frame+32 into RAM`0x20000544` (file key), then frame+16 into
RAM`0x20000554` (metadata). Native DATA uses the master configuration for
its first pass, copies that result back into the raw DATA buffer, then uses
the file configuration for its second pass. Both passes process16-byte blocks.

The file is described as encrypted, but its recovery uses AES's forward
operation twice, rather than an ordinary single AES-decrypt call. This was
the important distinction missed by the initial candidate tests. No IV or
chaining state is required in this fully verified transform.

The decoded metadata is:

```text
00cc0100 84f05b25 04a1423a 84f0a425
```

Interpreted as little-endian words: body length`0x1cc00` (117760), body
XOR`0x255bf084`, packed code-length/hardware ID`0x3a42a104` (59656 code bytes,
ID`0xa104`), and executable XOR`0x25a4f084`.

## Verification

`extract_update_keys.py` independently reassembles230 captured DATA frames,
then verifies:

- All59656 executable bytes match the original CPU-view dump at`0x2000`.
- Both the executable XOR and whole117760-byte body XOR match the header.
- Applying the inverse transform recreates every captured ciphertext byte.
- An independent512-byte crypto-enabled result previously measured on the
  physical board (`ram_bypass_test/observed_source_crypto_1.bin`) matches
  the predicted two-pass AES result exactly.

The full decoded update differs from the later CPU snapshot in1809 bytes,
all in the vendor data/settings region at or above`0x1a000`. It is not
claimed that the entire updater body equals the configured board snapshot.

The body ciphertext SHA256 is
`d571168a27bba5bd93722b103cdd833b90f2beced0bf5b6c5d55ecc3a0f04929`;
the decoded update SHA256 is
`c3b065a937670b745c2a2a59b57b6e3e2a099e694ed10fa1a540d6559774249c`.
Full machine-readable checks and difference ranges are in
[key_extraction_result.json](key_extraction_result.json).

This validates this captured update/key profile. It does not establish that
every model, version or OEM uses this master key, or recover every secret
that might exist elsewhere in the chip. This is key extraction from the
bootloader plus verification, not a cryptanalytic break of AES.

## The proposed all-zero DATA test

Sending512 zero ciphertext bytes to a crypto-enabled, no-program diagnostic
would produce32 identical output blocks for this profile. Each is predicted as:

```text
3af0e14399d7995a4a47d0225a90d8d1
```

`zero_input_prediction.bin` saves that prediction; it is **not a new physical
measurement**. A zero-input oracle alone normally gives a cipher output, not
the key. Here the static constant and existing measurements already supplied
a complete validation, so a live experiment was unnecessary and was not run.
An unexecuted read-only source-capture design was discussed; no new live probe
or flash programmer was installed.

The current VIA RAM keymap/macros/layout were read and backed up first under
`via_backup_before_zero_probe/`. No reboot or configuration change followed,
so no restore was needed. That backup is local configuration data and is not
required for reproducing the cryptographic result.

## Reproduce offline

From the workspace, using its existing Python environment/dependencies:

```powershell
$novaPython = '<LOCAL_USER>\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $novaPython crypto_research/offline_key_audit.py
& $novaPython crypto_research/extract_update_keys.py
```

`offline_key_audit.py` tests4096 standard AES/SM4 direction/layout/header
hypotheses and records the matching AES-forward metadata case.
`extract_update_keys.py` performs full validation and writes
`master_key.bin`, `captured_file_key.bin`, `captured_header_metadata.bin`,
`captured_update_ciphertext.bin`, `captured_update_plaintext.bin` and the
zero-input prediction. These outputs are not included in this repository. Neither script opens a device or produces an
installable firmware package.
