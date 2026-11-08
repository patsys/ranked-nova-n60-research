# Emergency boot selection in the research QMK image

The first physically flashed research image failed USB enumeration. The initial Esc+Fn reconnect did not recover it, but a later Esc-alone reconnect did; stock was restored. Later diagnostic V1 automatically returned to the bootloader after its USB timeout and its trace was retrieved. Diagnostic V2 now enumerates as QMK+VIA and passes protocol/remapping checks. Physical cold-power/key-hold validation of this final image remains outstanding. See `qmk_flash/SUCCESS_20261103.md`. Prior flashed artifacts are retained in the build archives.

The application checks held keys after clock and matrix initialization and before USB initialization. The default accepts **any populated key** that remains active for three consecutive acquisition batches. Different keys do not count as a continuous hold, and unpopulated positions are excluded.

Startup now reproduces original `0xea20(4,0)` clock/trim setup after domain setup, reading the actual factory word at `0x10000234`. The captured word `0x06a20060` selects nominal48MHz. Calibration failure or another effective nominal frequency requests the preserved bootloader because current delay loops and SysTick assume48MHz. Matrix initialization then uses original long-delay argument100 before GPIO configuration and argument300 afterward, before acquisition clock-gate/register setup. These are original `0xdd80` units, not verified milliseconds. The separate legacy RAM-probe initializer retains its previous behavior.

Configure at rebuild time in `keyboard/config.h`:

- `NOVA_EMERGENCY_HOLD_MODE=1`: any populated key, the default.
- `NOVA_EMERGENCY_HOLD_MODE=2`: Esc only, bank0/channel0.
- `NOVA_EMERGENCY_HOLD_MODE=0`: disable this application hook.
- `NOVA_EMERGENCY_HOLD_SCANS=3`: required consecutive scans, valid range1..255.
- `NOVA_EMERGENCY_READINESS_ATTEMPTS=100`: maximum batches, bounded1..1000.
- `NOVA_EMERGENCY_RETRY_LONG_UNITS=1`: original long-delay argument per retry.

The hook uses real custom acquisition and recovered hysteresis (>30 presses, <20 releases). It directly reads custom scan state while interrupts remain masked. Empty or unsettled batches now restart the consecutive hold count and continue checking, rather than abandoning the whole startup check immediately. It makes at most100 batches by default, calling the original long-delay helper with argument1 between attempts. A hold beginning later can qualify if three consecutive batches fit before the deadline. No-key startup incurs the complete bounded window. This is a count-based filter, not a measured duration or calibration claim. An interrupt-dependent `wait_ms` would deadlock while SysTick interrupts are masked and is not used here.

If a key is held, `bootloader_jump()` writes `0x5ac396c5` to retained register `0x4001400c`, then requests ARM SYSRESETREQ by writing `0x05fa0004` to AIRCR `0xe000ed0c`, with interrupts masked and data barriers. These values match the original application's recovered boot-entry sequence. `mcu_reset()` requests the core reset without adding a boot request. Neither primitive contains an EEPROM reset, flash erase, flash programmer, or option-byte writer.

Recognized initialization failures now request the preserved bootloader: reason1=matrix/settling failure, reason2=USB initialization failure, reason3=clock calibration failure, reason4=unsupported effective nominal frequency. Generic processor faults and failures before these checks are not redirected blindly. The held-key window precedes USB initialization, but any reset path still requires execution to reach its code.

## Offline evidence

`scan/validate_cold_fix.py` builds only an isolated ARM test ELF, without rebuilding firmware targets or installation manifests. Its15 passing cases verify argument100 precedes GPIO writes, argument300 precedes ADC/gate writes, initial empty/50-batch delayed readiness, final-three-attempt acceptance versus final-two rejection, rotating/absent/unrelated keys, bounce, bounded idle timeout and delay-failure exits. Results are in `scan/cold_fix_tests/result.json`.

`test_emergency_boot.py` executes the actual compiled basic and VIA ELFs. Updated fixtures include late-held keys and recognized clock/matrix/USB failure routes, both reset primitives, and original bootloader selection using the emitted request. The final step executes original reset/main with captured information-block bytes and modeled MMIO; it reaches USB-server selection at `0x848` and confirms the request is cleared. Its JSON identifies the exact tested ELF hashes; old-image results do not validate edited sources until rebuild and rerun.

The corrected linked images passed41 cases. Every call must return to its sentinel or reach an explicitly modeled reset/USB stop boundary; instruction-budget exhaustion cannot count as success. `emergency_boot_validation.json` records `completion_boundaries_checked=true` and the tested hashes.

Analog samples0/100, replay of captured factory word`0x06a20060`, clock-ready state and delay interception are explicit fixtures. These offline checks do not measure physical delay duration or sensor behavior.

## Limits

This remains application-level recovery. It cannot help if reset/vector handling or execution before the checks fails. The new settling, calibration and readiness window address concrete omissions, but the cause of the prior physical failure remains unconfirmed. Cold-start sensor timing and this corrected hold behavior still require physical validation. Resting values above30 could falsely select boot mode; Esc-only narrows inputs without proving calibration. Three batches do not establish a particular number of milliseconds.

The retained request is intended for the original core-reset sequence. Removing power is not a method for preserving a previously written request. The key must be held when the application executes the hook on its next start. None of this replaces an independently tested stock-firmware restore procedure.
