# Native update address bounds and supplied-stub audit

**The captured application-update mode1 starts at0x2000, but native mode0 can route an erase/program command to boot page0. No software rule in the supplied vendor stub rejects pages0–15. This proves command reachability under the stated offline model, not physical erase permission or successful bootloader overwrite.** Do not treat the original updater or its ACK alone as an application-only write boundary.

No USB/device access, installation, erase, or persistent-device write was performed by this audit. Reproduce with `firmware_dump/audit_flash_bounds.py`. Results: `flash_bounds_audit.json` contains25 START/DATA cases and two COMPLETE metadata-function cases. Root's independent supplied-stub boundary tests are in `boot_safety_audit/stub_page_boundaries.json`.

## Model and limits

The script executes original boot reset/scatter initialization through main0x700, then original outer update handler0xbdc, native START0xf00, original stub copy/XOR check and supplied440-byte stub instructions. It uses original initialized RAM ABI thunks and native wait/interrupt-mask helpers; those helpers are **not mocked to return success**. RAM guard words0x20000754/758 are initialized to5a5a5a5a/a5a5a5a5; DATA itself sets the third guard5555aaaa before its erase call. Peripheral registers are emulated RAM with busy clear, so controller permission/error semantics are not modeled.

Explicit substitutions: receive/send callbacks supply complete frames and collect replies; cryptographic helper0x29c supplies accepted decoded START metadata and an address-path DATA transformation. Algorithm/key validity and real ciphertext acceptance are not established by these tests. The unchanged captured encrypted header supplies the original shape; mode byte6 is outside the transformed16-byte blocks, and the native code does not include it in the decoded metadata equality checks. We do not claim a newly encrypted mode0 packet was tested on hardware.

Some end-boundary tests inject a documented prior DATA state (`r6=sequence-1`, remaining=`image_length-(sequence-1)*512`) rather than executing all preceding pages. The supplied receive callback bypasses the lower USB reassembly routine. In particular, a516-byte DATA-payload case demonstrates an outer-handler omission only; it is not proof such a packet traverses the real bounded receive/reassembly path.

## Native START checks and base selection

The captured START is496 bytes:488 payload bytes, stub length440 at packet+0x30, stub bytes at+0x34, trailing stub XOR word. Native0xf00:

* Stores header byte6 to configuration0x200001ec+0x14 at0xf34.
* Requires payload length488 at0xf54..0xf5c.
* Processes the two16-byte header blocks through its native compare/crypto branches.
* Compares packet halfword+2 times4 with the clear image-length word from packet+8 at0xfd2..0xfda. Thus this particular equality caps accepted clear length at0x3fffc; that is larger than the recovered128KiB flash and is **not** a safe application-region bound.
* Compares the decoded low16-bit version field with the clear version at0xfdc..0xfe0.
* Requires supplied stub length440, copies that length to0x20000000, compares XOR against the supplied trailing word, then initializes its timing through0x22c.

The outer handler0xcd4 then selects the base:

|Mode byte6|Native behavior|
|---|---|
|0|Writes base0 to config+0x2c at0xce2..0xce4|
|1|Requires config+0x20 <= config+0x18, then writes base0x2000 at0xcf0..0xcf4|
|Other|NACK5, returns without DATA dispatch|

The decoded metadata-length word and clear total-transfer length are distinct fields. A test where decoded metadata length differs by4 passed START; do not substitute a presumed equality between them. The high16 bits of another decoded word become a byte length by shifting left2 and are checked against decoded metadata length in mode1.

## DATA page calculation and captured end boundary

DATA requires an active START state and its byte sequence equal to `r6+1` at0xd14..0xd20. It checks payload against remaining transfer bytes, optionally transforms/decrypts, and computes the page argument as:

```text
page = (config.base >> 9) + r6
erase wrapper0x214 -> supplied stub+0x24
program wrapper0x220 -> supplied stub+0x6c
```

The captured length0x1cc00 is230 full512-byte pages. Under mode1 these are pages16..245, CPU bytes0x2000..0x1ebff, ending exclusively0x1ec00. Boundary state tests prove the last packet sequence230 reaches page245, while a further512-byte DATA at sequence231 with zero remaining is rejected before erase/program.

Other tested states:

|State|Observed native calls/results|
|---|---|
|Mode0, first DATA|Erase page0 and program page0; supplied stub emits controller commands,128 data-word stores; ACK4|
|Mode1, first DATA|Same operations on page16; ACK4|
|Mode1, length0x1e000, sequence240|Page255 accepted by supplied stub|
|Mode1, length0x1e200, sequence241|Native calls page256; supplied stub rejects2 without page-command stores. Caller continues and attempts checksum read beyond mapped128KiB at0xe46|
|Mode1, sequence255 with larger accepted length|Native calls page270; supplied stub rejects2; subsequent checksum read faults in the bounded CPU-image model|
|Sequence256|Packet byte wraps0; cannot equal arithmetic256; NACK before erase/program|

The0xe46 faults above are **emulation read faults**, not an assertion that silicon would fault the same way. They demonstrate lack of a preceding physical128KiB upper-bound check in the executed outer path.

The caller does not inspect erase/program return codes at0xe14..0xe38 before continuing. Native ACK4 alone therefore cannot establish a successful flash operation. Short or zero DATA payload cases also reach a full512-byte supplied-stub program loop; the primitive itself always consumes128 source words. A prospective host/writer must not infer that DATA payload length limits the physical page footprint.

## Supplied stub limits and controller bitmap

Erase stub+0x24 rejects only unsigned page>255. Program stub+0x6c rejects page>255, null source, or unaligned source. Neither imposes a lower bound16. For accepted page, the software writes one-hot `1 << (page&31)` to `0x400130d0 + 4*(page>>5)`, issues its controller command, then clears the bit. Command addresses use `page<<7` word indices; the program loop ORs word indices0..127 and writes128 words.

The captured boot patch-list writes to0x400130e8 and0x400130ec overlap bitmap banks6/7 by this same arithmetic, corresponding to pages192..223 and224..255. The software relationship is established, but physical bit permissions, write locking, aliases, and hardware protection are unknown. In particular, the valuesffff0000/ffffffff do **not** by themselves prove that attempts to select page0 would succeed or be blocked.

## COMPLETE reaches a separate metadata erase/program path

Original COMPLETE dispatch at0xe7e checks active state. At0xe90..0xeb4 it compares declared total byte count, accumulated incoming XOR, readback XOR, and code-region XOR against stored fields. On success it copies fields from the COMPLETE payload, loads base config+0x2c, and calls0xae8 at0xed2.

The audit executes0xae8 separately for modes0/1 with the actual captured512-byte metadata block mapped at CPU0x10000600. It does not claim the entire COMPLETE packet/checksum sequence was synthesized successfully. The native function constructs a replacement512-byte metadata image and unconditionally calls special erase wrapper0x1fc -> stub+0xda, then special program wrapper0x208 -> stub+0xfc. Both were executed with the original RAM ABI and helpers.

Observed controller address stores are special word address0x10180 for erase, then0x10180..0x101ff for128 program words. That is distinct from ordinary application pages; the apparent relationship to CPU hidden metadata0x10000600 is supported by the native source copy/metadata update, but the controller's address-space encoding is not independently documented. COMPLETE is therefore a persistent metadata mutation, not merely a finish/reset command. A rollback plan limited to the128KiB CPU flash dump omits this separately captured block.

## Requirements for a future bounded writer

These are design constraints, not an implemented or authorized flasher:

* Enforce application-only page bounds **inside the replacement RAM stub**, independently of mode/header/host checks. For the currently reserved0x2000..0x19fff code region, allowed full pages would be16..207; preserve0x1a000 onward unless a separate verified layout explicitly authorizes those data writes.
* Reject short/non-page DATA for programming, check full512-byte aligned RAM source bounds, use unsigned comparisons, and validate rounded image end without overflow before any erase.
* Check and propagate every erase/program result, then compare readback, with an independent digest for boot and preserved persistent regions.
* Treat COMPLETE's hidden metadata erase/program as a separate explicit operation. Do not invoke it blindly or assume application-only page bounds contain its special address space.
* Establish physical controller protection/restore/recovery behavior before calling a writer safe. These offline command traces supply evidence for review; they do not close those hardware questions.
