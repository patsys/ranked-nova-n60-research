# Ranked Nova 60% — Firmware, Protocol & Encryption Reverse-Engineering

> **Historical report, not current status.** Start with
> [the end-to-end guide](REVERSE_ENGINEERING_GUIDE.md). QMK/VIA was subsequently
> installed successfully and the user confirmed operation on2026-11-03.
> The AES transform and update key were later recovered; see
> [key extraction](../../research/02-update-crypto/KEY_RECOVERY.md). The exact MCU part remains unidentified. Early
> assertions below that QMK cannot run, that a particular cipher/KDF is proved,
> or that ciphertext must reach physical flash unchanged are superseded.

**Device:** Ranked Nova 60% mechanical keyboard, German (DE / ISO) layout
**Report date:** 2026-11-02

**Later live-test correction:** SQLite findings 33 onward and the
`readonly_stub` notes extend this original report. Custom RAM code executes,
timing can return register/code values, and the programmer's source word for
captured ciphertext `f0 6d 17 be` was measured as `50 1c 00 20` in repeated
transfers. This disproves the inference below that unchanged USB ciphertext
necessarily reaches flash unchanged or proves transparent XIP decryption.
Bootloader-side transformation before programming is now directly supported;
decryption is the leading explanation. See `readonly_stub/BUFFER_TRACE.md`
and SQLite finding 41. Later tests also established direct custom USB replies
and bounded CPU code reads: see `readonly_stub/USB_READ_CHANNEL.md` and
SQLite findings 43–45. The original limitations below are historical where
superseded by those live-test findings.

**Verified firmware dump:** Findings 46–47 add a 56-byte USB block reader and
two byte-identical CPU-visible reads of the full 128 KiB flash range. The
8 KiB bootloader, application region at 0x2000, hashes, readable disassembly,
and raw evidence are in `firmware_dump/`. The binaries are also stored in
SQLite table `firmware_dumps`. See `firmware_dump/README.md` for verification
and the distinction between CPU-visible plaintext and physical flash/SWD.

**Artifacts:** `ranked_re.db` (SQLite, 32 findings + 11 tables), `firmware_diff.html`, raw captures (`fw_update.pcap`, `layout_cap.pcap`, `nova_cap.pcap`), extracted `stub.bin`.

---

## 1. Historical executive summary

- The keyboard is an **ODM / white-label board on the Royuan ("RY") firmware platform** — the same platform behind MonsGeek, Akko, Epomaker and others. It is **not** a QMK/VIA design.
- The complete **vendor USB-HID control protocol** was decoded and verified live: key remap, per-key RGB, macros, key-triggers, music/visualizer, and bootloader entry.
- The firmware update is **genuinely encrypted** — a **custom 128-bit block cipher in ECB mode**, with **per-file keying** and the key held **on the chip**. The PC does **zero** decryption; it streams the ciphertext verbatim and the keyboard decrypts in hardware.
- The full **flash memory map** and cross-version structure were recovered **despite** the encryption, by exploiting ECB's structural leakage.
- **Decryption is not possible from software** (ciphertext-only against a strong cipher whose key and algorithm live on the chip). The only routes to plaintext are hardware / bootloader exploitation.
- **QMK cannot be installed on this unit**: locked encrypted bootloader, an obscure Yichip-class MCU with no QMK port, and Ranked publishes no QMK firmware/source despite advertising "optional QMK/VIA support."

---

## 2. Device identity

| Attribute | Value | Evidence |
|---|---|---|
| Product | Ranked Nova 60% (N60), DE/ISO layout | `Dev.ini` Name="Nova 60%", Layout2=DE→A0A3; USB strings |
| USB strings | Mfg `Ranked`, Product `Nova 60% Keyboard`, Serial `rankednova` (hardcoded), bcdDevice `0x0004` | HID descriptor query |
| App USB id | **VID 0x3532 / PID 0xA0A3** — composite (MI_00 boot keyboard + MI_01 vendor HID, usage page 0xFF00) | Windows USB enum registry |
| Bootloader USB id | **VID 0x352D / PID 0x1101** — HID-class bootloader | `update_config.ini`, live enumeration |
| Platform / SDK | **Royuan (RY)** | DLL PDB path `Ry_Online_Update` / `pc_sdk_tool`; MonsGeek/Akko ship the same `royuan_tool.exe` / `ry_upgrade.exe` |
| MCU | **32-bit ARM Cortex-M0**, Chinese vendor — most likely **Yichip YC-family** (YC500 class). **Ruled out:** Artery AT32F405 (=RY5088, the magnetic boards) | ARM Thumb flash stub; flash controller at 0x40013000 (AT32 uses 0x40023C00); different bootloader VID/protocol |
| Flash | ~128 KB: resident bootloader + ~96 KB app partition (≈59.6 KB real code) + data partition | ECB structure map; erased run ends exactly at 0x18000 (96 KB) |
| Firmware security | App partition encrypted (`encryption_en=1`); custom 128-bit ECB; on-chip key | see §4 |

**Ecosystem chip map** (from MonsGeek driver assets + community RE): RY5088 = Artery AT32F405 (magnetic boards; firmware is *plain .bin*, no encryption, SWD-dumpable); Yichip YC500 / YC3121 / YC300 (wired / Hall-effect); Beken BK100 (wireless). This board is an **older, encrypted generation**; the newer AT32F405 boards dropped encryption and are community-cracked (`dot-agi/ry5088-flasher`, `monsgeek-akko-linux`, `keylume`).

---

## 3. Vendor HID control protocol (decoded + verified)

64-byte reports on interface MI_01, usage page 0xFF00, report layout `[0x04 report-id][cmd][args…]`. The device echoes the command id as an acknowledgement.

| Cmd | Function | Notes |
|---|---|---|
| 0xA0 | SetMatrix (key remap) | `[04 A0 02 04 page 0E layer]` + 4-byte entries `[matrix_index][0xFC][00][HID usage]`, 4 layers × 14 pages, trailer `A5 00 00`. Verified against `Dev.ini`. |
| 0xA5 | ToBootloader | `04 A5 01` — enter the HID bootloader (confirmed live) |
| 0xA7 | MallocMacroID | |
| 0xA8 | SetMacro | |
| 0xAE | SetLED | `[AE][01][00][00][nLED][nSpeed][nLight][nColor]`, byte7=0xFF in per-key mode |
| 0xB1 | SendMusicData | audio-visualizer stream (the `ET\*\audiobar.txt` / `stream_h.txt` data) |
| 0xB6 | SetKeyTrigger (resp 0xB7) | per-key actuation config |

Features: full HID keyboard, 4 layers (Fn1/Fn2/Tap), per-key RGB + ~20 hardware effects, macro engine, key-trigger config, audio visualizer.

---

## 4. Firmware encryption (historical interpretation)

**Superseded interpretation:** the initial analysis did not identify the cipher
or key. Later bootloader extraction and complete offline verification identified
two AES-forward passes and the master/per-file keys for the captured update.
The assertions below record the initial hypothesis, not that later result.
See the current [process guide](REVERSE_ENGINEERING_GUIDE.md).

- **Genuinely encrypted**, not obfuscation. `.enc` files under `Dev/kb/RD61/.../Update/<variant>/usb_hid_app_vX.X.X_<hash>.enc`.
- **Custom 128-bit (16-byte) block cipher in ECB mode** — proven by block-repetition (dominant blank-flash blocks repeat thousands of times). **Not** AES/SM4/TEA/XTEA (no matching S-boxes/constants), **not** repeating-XOR (tested: dominant blocks XOR ≠ all-FF), **not** byte-wise/positional (measured full diffusion — random ciphertext-block pairs match at the 1/256 rate).
- **Per-file keying:** key = KDF(on-chip base secret, per-file salt). The **32-byte header** at the start of every `.enc` is the salt/indication carried with each file. Every variant and every version uses a different effective key → zero shared ciphertext blocks across files.
- **Filename hex suffix = 32-bit XOR checksum** of the whole `.enc` (verified on 4 files) — the integrity tag the DLL checks (`DAT_101cd608`) before flashing.
- **The PC performs no cryptography.** `UsbHid_v1.0.6.dll` (`FUN_10004e40`) reads the `.enc`, verifies the XOR checksum, and streams the bytes **unchanged**. Dynamic capture confirmed all 7,360 payload blocks appear verbatim on the wire (100% coverage). Decryption happens on the keyboard chip.

**Why it can't be decrypted from software:** ciphertext-only against a 128-bit key is brute-force-proof; known-plaintext (the blank blocks) gives no leverage on a cipher with full diffusion; the algorithm itself is on the chip, so no weakness can be found or exploited. Both the key and the algorithm are sealed in silicon.

---

## 5. Flash update mechanism

- Enter bootloader: app receives `04 A5 01`; device re-enumerates as VID 0x352D PID 0x1101.
- Bootloader handshake: host sends `getv` (framed `[00 00 00 00][04][00 00][01]"getv"`), device replies `[…][10][…]"version:"` + hardware-id `0xA1` + version fields.
- Firmware transfer (the "operational" channel, `s`/`w` magic bytes 0x73/0x77): START `01…` carries metadata + image size (0x1CC00) + hw-id + the encrypted 32-byte header + a **plaintext ARM flash stub** (length-prefixed), then DATA `02…` streams the encrypted body, then COMPLETE.
- **The flash stub** (440 bytes, embedded in the DLL at file offset `0x1A5140`, uploaded to RAM 0x20000000) was extracted and decompiled. It is a **pure flash programmer, not a decryptor**: unlock+wait (`0x00`), sector-erase (`0x24`, CR=2), page-program (`0x6c`/`0xfc`, 512-byte pages, writes data words verbatim — no XOR/cipher/key), timing config (`0x13a`). Flash controller base `0x40013000`, registers `CR@0 / ADDR@4 / DATA@8 / status@0x10`, 512-byte pages.
- **Consequence:** the encrypted firmware is written to flash unchanged, so decryption is a **hardware feature of the MCU** (transparent XIP flash-decrypt engine with an on-chip/OTP key). Even a raw SWD flash dump would return ciphertext; plaintext exists only on the CPU side of the crypto engine.

---

## 6. Flash memory map & version analysis (A0A3 v1.0.4)

| Image offset | Size | Region |
|---|---|---|
| 0x00000–0x000C0 | ~192 B | header / vector table |
| 0x000C0–0x0E910 | ~59.6 KB | main application code (contiguous) |
| 0x0E910–0x18000 | ~38 KB | erased flash (ends exactly on 96 KB boundary) |
| 0x18000–0x1CC00 | ~19 KB | data partition (almost all zero-fill) |

**Version diff (v1.0.3 → v1.0.4):** the real code region is the same size (±2 blocks); the entire +1,536-byte file growth is the zero-filled data partition expanding. So the update is almost entirely a data-partition change, not code — recoverable from ECB structure even though per-file keys make the bytes incomparable.

**Firmware variants on disk:** 31 `.enc` files across 15 layout/hardware variants (RD61 61-key A0A1/A0B1; RD61 62-key A0A2–A0A7, A0B2–A0B7; RD68 68-key-US A0C1). A0A3 = the German layout (this unit). Per-unit keys are **ruled out** (one `.enc` flashes all units of a variant); keys vary per product/version. Whether the base secret is platform-wide or per-OEM can't be decided from ciphertext alone.

---

## 7. Live bootloader reconnaissance (non-destructive)

- Established reliable two-way HID comms (65-byte reports, overlapped I/O). `getv` works and returns version/hw-id.
- Probed 14 other read/info ASCII commands — **all ignored**; the only recognized safe command is `getv`. There is **no read/dump/info primitive** to extract memory safely.
- **The erase is stub-side, not forced:** the erase routine lives inside the uploaded stub, and entering the bootloader does **not** erase (we entered repeatedly and the app kept working). So a custom read-only stub could run without wiping the firmware (worst case recoverable by a replug).

---

## 8. The only remaining route to plaintext (design, not executed)

Extracting the key / plaintext requires **active bootloader exploitation**: upload a **custom read-only ARM Thumb stub** via the plaintext stub channel (the encryption does **not** cover the stub), get the on-chip ROM to run it, and have it read chip memory (OTP/key, or the decrypted flash via the CPU bus) and exfiltrate it through the ACK channel. This **sidesteps SWD readout protection** because it uses the vendor's own bootloader.

Open unknowns that decide success (discoverable only by experiment): (1) whether the ROM authenticates the stub before running it; (2) the ROM↔stub calling/exfil convention (lives in the un-dumped ROM — black-box); (3) whether the key or decrypted flash is CPU-readable. This is a genuine firmware-exploitation project; it was **not performed**. The community projects for the sibling RY5088/AT32 platform are the natural place to pursue comparable work.

---

## 9. QMK / VIA feasibility

**Not possible on this unit**, three independent blockers:
1. No QMK port exists for its obscure Yichip/Royuan Cortex-M0 (QMK supports STM32/GD32/RP2040/WB32/AT32/AVR — none of which this is).
2. The bootloader only accepts the vendor's encrypted, checksummed `.enc`; an unsigned QMK image is rejected and would be scrambled by the hardware decryption.
3. Ranked publishes no QMK firmware, source, or flashing instructions; the board is not in the QMK repository — despite the advertised "optional QMK/VIA support."

The "QMK support" selling point was never delivered for this hardware. Remedies: (a) hold Ranked to the claim (request the firmware or a refund/replacement — see the drafted support request); (b) for the actual goal (a portable layout such as **Neo2**), use a genuine QMK/VIA keyboard (e.g. ZSA Voyager, Keychron V/Q) — its layout lives in the keyboard and works on locked/corporate laptops with no host software.

---

## 10. Deliverables

- **`ranked_re.db`** — SQLite database, the full machine-readable record: **32 findings** plus tables `functions`, `edges`, `call_graph`, `decompiled`, `strings_of_interest`, `usb_commands`, `setmatrix_format`, `remap_capture`, `dynamic_capture`, `fw_memory_map`, `firmware_variants`, `firmware_identity`, `flash_controller`, `ecosystem_chips`.
- **`REPORT.md`** — this document.
- **`firmware_diff.html`** — visual v1.0.3 vs v1.0.4 block-map diff.
- **`findings_export.txt`** — plain-text dump of all findings (generated alongside).
- Raw captures and `stub.bin` for anyone continuing the work.
