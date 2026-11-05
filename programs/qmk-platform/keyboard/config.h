#pragma once
/* Evidence: original 0x4cb0, literal tables 0xf61a/0xf660. */
#define MATRIX_ROWS 6
#define MATRIX_COLS 11
/* Physical diagnostic: late ADC channels were mostly zero during held keys,
 * with sporadic valid peaks. Extend the bank-high conversion window for a
 * bounded timing trial; thresholds and peripheral register values are unchanged.
 * Original helper units, not measured microseconds. Original baseline was 5.
 */
#define NOVA_SCAN_CONVERSION_SETTLE_UNITS 20
#ifdef RGB_MATRIX_ENABLE
#define RGB_MATRIX_LED_COUNT 62
#define RGB_MATRIX_DEFAULT_MODE RGB_MATRIX_SOLID_COLOR
#define RGB_MATRIX_DEFAULT_SAT 0
#define RGB_MATRIX_DEFAULT_VAL 96
#define RGB_MATRIX_MAXIMUM_BRIGHTNESS 128
#define RGB_MATRIX_LED_FLUSH_LIMIT 16
#define ENABLE_RGB_MATRIX_CYCLE_ALL
#define ENABLE_RGB_MATRIX_BREATHING
#endif
/* Emergency boot selection uses recovered raw analog scan state before USB.
 * 0=disabled, 1=any populated key, 2=Esc(bank0/channel0). Changes require rebuild.
 * Three scans of the SAME key must remain active; physical timing/calibration
 * is unverified. No EEPROM reset or flash operation is performed by this hook.
 */
#ifndef NOVA_EMERGENCY_HOLD_MODE
#define NOVA_EMERGENCY_HOLD_MODE 1
#endif
#ifndef NOVA_EMERGENCY_HOLD_SCANS
#define NOVA_EMERGENCY_HOLD_SCANS 3
#endif
/* No guessed MCU, clock source, diode direction, digital matrix pins, or
 * EEPROM region: this keyboard needs a custom analog acquisition backend.
 */
