# USB outer IRQ status/ACK ordering

The original application vector20 points to Thumb address `0x312d`, external
IRQ4. Its dispatcher at `0x312c` does not reuse the status-test word for ACK:

| Original instruction | Access |
|---|---|
| `0x3130` | Read `0x40016008`, test bit0 |
| `0x3136` | If bit0 was set, **read again**, ACK using this word AND2 |
| `0x313e` | Dispatch event handler `0xebf0` |
| `0x3142` | Read `0x40016008`, test bit1 |
| `0x3148` | If bit1 was set, **read again**, ACK using this word AND1 |
| `0x3150` | Dispatch auxiliary handler `0xf310` |

The previous C dispatcher reused the preceding test value when constructing
each ACK. Its writes matched native code under stable status fixtures, but
its reads did not. The corrected C reads immediately before each ACK, preserving
the native ordering. The old source is retained as `ranked_usb_device_before.c`.

`test_outer_irq.py` executes actual native outer instructions and actual before/
fixed compiled C. Inner event and auxiliary calls are intercepted at explicit
callback boundaries to isolate the dispatcher. Seven cases compare exact
ordered status reads, ACK writes, callback order and modeled pending state:

- Stable status0,1,2,3. Native/fixed status-read counts are2,3,3,4; previous C
  used2 for every case.
- Auxiliary bit arrives immediately after the initial event-bit test. Under
  the explicitly modeled write-zero-clears latch behavior, native/fixed code
  preserves and dispatches it; cached C loses it.
- Event bit arrives immediately after the auxiliary-bit test. Native/fixed
  code preserves it for the next IRQ; cached C loses it under the same model.
- Event bit arrives after an initially zero first test: native/fixed behavior
  leaves it pending for a later IRQ rather than fabricating immediate dispatch.

All seven corrected traces exactly match native traces; result/source hashes
are in `outer_irq_validation.json`. Every emulated call must return to its
sentinel, so exhausting the instruction budget cannot pass.

The conditional write-zero-clears model is an inference consistent with the
native mask operations, not a verified vendor register specification. This
audit establishes a software ordering discrepancy and removes it; it does
**not** establish that the discrepancy caused the physical enumeration failure
or that an actual IRQ storm occurred. Inner event4 reset and endpoint callback
behavior are covered by separate native/C tests, not replaced by these synthetic
callback boundaries. No hardware access or flash operation was performed.
