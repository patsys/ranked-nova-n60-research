# Boot updater polling and application-vector dependency

**Boot USB has a native polling path, but asynchronous exceptions still forward through the application vector table. Rewriting identical stock vectors was not a test of replacing them with QMK vectors. Changing page order alone does not remove this dependency.**

No hardware was accessed for this audit. Source boot SHA256: `e46c6d9300a13f4d2eea7c16584d24ea6e4e1b83815e5f84f389d4aeb0915f62`.

## Exception forwarding

The native exception vector entries point to0x1df. That trampoline branches to0x3ad. Original0x3ac reads IPSR, shifts it left2, adds0x2000, loads the word there, and branches through it. It does not test a boot/updater-mode flag and does not provide an independent boot USB ISR table. This includes NMI/HardFault and the implemented external IRQ slots. The existing `vector_forwarding_validation.json` executes27 synthetic IPSR cases against that exact code.

Consequences during changed application writes:

* Writing the vector page first can immediately point exceptions at QMK handlers whose code/data is not written or initialized yet.
* Writing vectors last keeps stock exception targets, but earlier QMK body writes can replace the stock handlers. For example, stock IRQ4 points to0x312d and the stock SysTick path uses other application code. Thus vectors-last alone is insufficient.
* PRIMASK masks ordinary configurable interrupts, including SysTick, but does not mask NMI/HardFault. Disabling NVIC external IRQs alone does not establish that SysTick cannot fire.

## Actual polled boot USB path

The boot updater's receive callback0x10e8 calls the native USB event poller0x1278 at0x1106 while waiting for a complete frame. The boot enumeration initializer0x1158 likewise calls0x1278 from0x11bc while waiting for USB configured state. Poll0x1278 reads peripheral status at0x40016008, then processes events from the0x40017e80 bank. Boot OUT endpoint4 FIFO bytes are copied through0x3ee ->0x10cc into the receive frame; native reply0x1124 ->0x594 writes the interrupt IN FIFO.

These routines are reached by ordinary branches/calls, independently of exception forwarding. Original delay helpers0x9bc/0xa14 use CPU loops and stored clock calculations rather than a required SysTick interrupt.

`audit_boot_poll_irq.py` executes the actual OUT polling/reassembly, native GETV handler, and native TX with an emulated USB packet/event fixture. Four cases pass:

|Application image|PRIMASK|Result|
|---|---|---|
|Original|0|Correct GETV reply; no application data/vector reads|
|Original|1|Same reply; mask unchanged|
|Erased from0x2000 onward|0|Same reply; no application reads|
|Erased from0x2000 onward|1|Same reply; mask unchanged|

The script supplies peripheral event/FIFO storage and skips delay0x9bc for speed. It does not synthesize asynchronous interrupts or model USB electrical behavior. Therefore it establishes that the native polling route can execute with PRIMASK1 and without application contents; it does not establish that real interrupt sources are absent.

## Native interrupt setup and preservation

The boot image's explicit global-mask operations are helper0x1d0 (`MRS PRIMASK; CPSID i`) and0x1d8 (`MSR PRIMASK,R0`). The supplied vendor operation bodies invoke these around individual controller operations and restore the entry mask. They do not independently establish a mask covering the entire multi-page update, reader handoff, and verification phase.

There is a native NVIC ICER helper0x238 writing one selected bit to0xe000e180. Crypto initializer0x330 calls it for IRQ7; the boot USB initializer calls0x330 with callback argument0, selecting its polling/IRQ7-disabled branch. A nonzero callback selects another branch that clears/enables IRQ7 through0xe000e280/0xe000e100. This is not a global NVIC-clear routine and says nothing about every peripheral/SysTick source inherited from an entry that did not reset the core.

## Implications for a changed-firmware transfer

A live preflight should report PRIMASK, NVIC ISER/ISPR, and SysTick control at0xe000e010, with the exact boot entry/reset path. Reading PRIMASK and ISER alone omits SysTick. A snapshot of disabled sources supports the current state but does not prevent a later source enable.

If the chosen design establishes PRIMASK1 before any application erase and keeps it through all changed-code writes/readback, the native polling path is compatible in the offline tests. The writer must preserve that mask rather than accidentally restoring0 through its helper calls, and a verified release/reset must establish the intended application startup state. This audit does not itself implement or authorize that new writer variant.

Neither vector-first nor vector-last is declared safe here. Ordinary IRQ suppression, the boot exception-forwarding rule, controller busy/fault behavior, single-reentry failure protection, and power-loss recovery must be considered together. NMI/HardFault and the absence of a proved application-independent recovery route remain material limits.
