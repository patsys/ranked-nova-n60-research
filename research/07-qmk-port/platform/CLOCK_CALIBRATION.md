# Original EA20(4,0) clock sequence

This correction is an offline implementation, not another firmware installation. The previously flashed research image omitted this original early-startup sequence. The omission is a concrete difference; it has not been proven to be the sole cause of that image's physical USB failure.

`nova_original_clock_calibrate_4_0()` transcribes the original function at `0xea20` with fixed arguments4 and0, including `0xeab4` and the priority initialization at `0xf3a8`. It:

1. Sets original bookkeeping fields08/0c to **`0x2000`**, the actual literal at `0xea9c`.
2. Reads the real per-device configuration word at `0x10000234`; preserves unrelated bits of `0x4001900c` while replacing its bits8..10 with `(word &0x70)<<4`.
3. Calls the original-unit short-delay callback with10.
4. Re-reads the factory word twice and writes `((word<<8)>>24) | ((word>>8)&0xf0000)` to `0x40019010`, preserving the original32-bit shift behavior and read order.
5. Calls the original long-delay callback with1.
6. Reads the word again and sets source bookkeeping to `24000000 +4000000*((word<<25)>>29)`. The extracted index is bits4..6, including bit6.
7. Writes divider0 to `0x40014018`, and sets effective bookkeeping equal to source frequency.
8. Applies the original priorities: SysTick2, external IRQ2 priority3, external IRQ4 priority1, through word read-modify-writes preserving other priority bytes.

Original bookkeeping addresses `0x20000428..0x20000437` are **not reused** because they overlap the new application's stack layout. Equivalent volatile C state is relocated by the linker. Accessors expose source/effective Hz and the observed word. The implementation reads configuration dynamically; the captured device value is not compiled as a trim constant.

The separate fixed-word read helper is `read_factory_clock_word.py`. Its builder accepts no arbitrary address or length and emulates exactly one four-byte information-region read plus bounded RAM reply/stack writes. Root's later explicit live read captured `0x06a20060`, giving source/effective48MHz, `0x4001900c` field `0x600`, and `0x40019010` value `0x600a2`. Evidence is stored under `firmware_dump/boot_safety_audit/factory_clock_*`. The original metadata-reader bounds remain unchanged.

## Validation

`validate_clock_calibration.py` compiles only an isolated validation ELF. It compares actual original `0xea20`, `0xeab4`, `0xf3a8` and `0x2ba8` instructions with the compiled C implementation. Thirty-seven equivalence cases cover every frequency index, zero/all-ones/random fields, three different initial register patterns, the live captured word, and four deliberately changing factory-read values. Ordered configuration/MMIO reads and writes, delay-call arguments and relocated bookkeeping all match. Four additional callback-failure fixtures check missing callbacks produce no hardware operations and a failing long-delay callback prevents later divider/priority changes.

The native comparison caught and corrected an early misreading of the bookkeeping literal as32; it is8192. This illustrates why the original-instruction comparison is required.

Tests model registers/configuration as RAM and bypass original delays. They do not prove oscillator/PLL settling, actual clock frequency, trim-register side effects, cold USB enumeration or recovery. The existing original-delay implementation assumes48MHz; startup integration must reject another effective frequency or supply an appropriately validated timing implementation. The live word predicts48MHz but is not a frequency measurement.

No complete target image or its manifest was rebuilt by this calibration task. Source SHA-256 and all event traces are recorded in `qmk_port/build/clock_calibration_validation/validation.json`.
