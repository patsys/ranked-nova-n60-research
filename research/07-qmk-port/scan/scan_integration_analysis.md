# Scan integration: recovered components and remaining dependencies

All validation work is offline. `recovered_scan.c` contains pure extracted
tables/helpers. `nova_acquisition.c` now implements the original acquisition
register sequence through real volatile MMIO callbacks, and
`qmk_port/keyboard/matrix.c` supplies QMK `CUSTOM_MATRIX=lite` entry points.
This is implemented runtime code, but the complete platform and physical timing
have not been validated on hardware.

The QMK integration acquires synchronously when QMK polls the matrix. It uses
the recovered per-bank delay arguments and hysteresis, while replacing the
vendor USB-event/SysTick scheduler with QMK polling. It does not promise the
vendor scan cadence or reproduce vendor report/event machinery.

## Normal event path

The recovered main loop at `0xce1c` calls `0x4fe4` at `0xce6a` when its software
countdown allows. `0x4fe4` uses state byte `0x200002d5` (base `0x200002cc+9`).
In state 1 it invokes `0x58d4`:

- `0x58d4` first requires the batch-ready byte `0x200002ca` to equal 1.
- For 11 channels it compares the latest six-bank bitmasks at `0x20000bae`
  with the previous masks at `0x20000bc4`.
- It stores XOR change masks at `0x20000cf4` and `0x20000d0a`, updates the
  previous masks, and marks the pending-event byte `0x200002cd` on change.
- It calls `0x4db8`, clearing the batch-ready byte so acquisition may run again.

`0x4fe4` advances to state 2 after the configured software countdown and calls
event-building `0x56a4`. This eventually translates original logical IDs through
configured maps and constructs USB key reports. A QMK port should feed the
observed bank/channel states into its own matrix/event code instead of copying
the proprietary report-generation machinery blindly.

## Acquisition scheduling and SysTick

`0xf2b8` checks a software byte and `0xf104` before starting a timer sequence:
it calls `0xeaec` with argument 40 and callback `0xead1`, then ORs 3 into the
SysTick control register `0xe000e010` (enable and interrupt bits). `0xeaec`
computes:

```
reload = (nominal_clock_hz / 1000000) * argument - 16
*(uint32_t *)0xe000e014 = reload
*(uint32_t *)0xe000e018 = 0
callback_at_0x2000036c = callback
```

The nominal clock accessor `0x4194` reads `0x2000042c`. Initialized data contains
48,000,000 there; the value may later be updated by clock setup. This is a
software clock claim, not an electrical measurement. With 48MHz, the arithmetic
yields 1,904 for argument 40 and 38,384 for argument 800. The recovered `-16`
is deliberate evidence; substituting the conventional SysTick `-1` would change
the original behavior. Absolute elapsed intervals depend on clock-source bits.

The SysTick vector dispatches via `0x30ec` to the RAM callback. The first callback
`0xead0` installs a new callback `0xeb1d` with argument 800, calls no-op `0x5d54`,
then invokes acquisition `0x4cb0`. The later callback at `0xeb1c` clears SysTick's
enable bit, calls no-op `0x5d56`, and updates software countdowns via `0xeb38`.
Thus this is a scheduled two-stage sequence, not simply a fixed periodic scan
loop. The native USB event handler calls `0x3078` directly at `0xed32`, and
`0x3078` calls `0xf2b8` at `0x3086`. This links acquisition scheduling to USB
events. The exact USB status bit/event type, upstream period, and all enable
conditions remain to be consolidated with USB analysis before adopting a frequency.
USB analysis further identified this branch as event-code **1** from low five
bits at `0x40016000`, acknowledged by writing 2 at `0x40017eac`. It is plausible
SOF behavior, but no vendor documentation confirms that name.

## Clock, pin, and acquisition initialization

The geometry and acquisition writes are documented in
`firmware_dump/key_scan_analysis.md`. In addition, `0x31b4` first calls `0xd524`
with mask `0x800` and enable argument 1. That helper writes the mask to
`0x4001402c` and delays using `0xdde8(10)`; the disable path writes
`0x40014030`. This dependency must precede acquisition register setup.

`0xdde8` selects a delay function using the nominal clock accessor. Its helper
table starts at RAM `0x20000470`; for a nominal 48MHz it selects index 12,
function pointer `0x21c9`. Delay arguments 10 and 5 inside acquisition therefore
cannot safely be replaced with guessed cycle delays during an initial port.

The code initializes the 11 acquisition pins to word `0x32`, restores them to
word `0x02`, and configures the six bank pins to word 1. GPIO meanings and bank
polarity are inferred from operation, not from a confirmed vendor datasheet.

The recovered scan path uses raw sample >30 / <20 hysteresis. It does not show a
per-key calibration table or an adjustable Hall actuation threshold in this
routine. Other configuration paths may affect acquisition gain, baseline, or
filtering; claiming a complete calibration algorithm would exceed this evidence.

## Validation and integration limits

`validate_scan.py` checks the C arrays against the original binary and decoded
RAM pointer table. It then executes the original acquisition routine at
`0x4cb0` for 14 cases covering sample values 0,19,20,25,30,31,65535 and both
initially clear/set bank bits. All 62 populated sample slots, hysteresis masks,
and active-position counts match the recovered behavior. Only the original
delay helper is bypassed. MMIO is modeled as memory storage, so these checks
prove extraction and algorithm interpretation, not hardware timing.

`validate_acquisition_compiled.py` additionally cross-compiles the actual C
acquisition implementation for Cortex-M0 and executes it in Unicorn. Its MMIO
read/write and delay-argument trace exactly matches original `0x4470+0x31b4`
initialization and 14 executions of `0x4cb0`. Bank-state masks match and QMK
six-row state conversion is checked. Results are in
`validation_build/result.json`. This catches register-sequence errors in the
compiled implementation; storage-backed MMIO still cannot establish electrical
timing or identify undocumented register meanings.

`recover_function_layers.py` extracts three original fallback layers into
`function_layers.json`. Original `0x33a0` recognizes held FF/FE selectors,
sets bytes `0x200002d7`/`0x200002d8`, and suppresses the selector positions from
normal reports. `0x3598` dispatches FF first to `0x32f0` (fallback `0xf79e`),
otherwise FE to `0x3348` (fallback `0xf89a`), otherwise base `0x35c0` (`0xf6a2`).
Thus these are two momentary alternate layers, with FF priority. FB actions and
B0..BF actions in alternate layers are vendor actions, not automatically valid
basic HID usages; their meanings must be recovered before translating them.

The remaining integration requires verified clock/reset/startup and USB,
appropriate scheduling under QMK, and physical validation without persistent
installation. This code does not install itself or access a flash controller.
