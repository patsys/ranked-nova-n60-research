# Optional USB runtime diagnostics

`NOVA_USB_DIAGNOSTIC` adds five runtime hooks declared by `runtime/usb_diagnostic.h`: IRQ entry/exit, status observations, raw event observations, configuration transitions, and auxiliary flags. `read32` first performs its original single volatile read and passes that value to the logger. There are no additional USB MMIO reads or writes. Raw event values are masked to the same five bits consumed by the transport. The configured hook runs for reset/deconfiguration as well as configuration.

The platform agent owns the retained RAM trace, timeout/recovery policy, and the hook implementation. These hooks alone do not guarantee recovery from a fault, interrupt masking, or hardware USB failure. They are diagnostic instrumentation, not proof that enumeration will succeed.

`validate_diagnostic_hooks.py` compiles basic and VIA variants both with and without the macro, verifies all five diagnostic hook references, and compares default executable sections against a saved pre-instrumentation source. Isolated test objects are stored under `usb/diagnostic_validation`; it does not rebuild deployable images or access hardware.
