#pragma once
#include <stdbool.h>
#include <stdint.h>

/* Recovered register operations, not a complete QMK platform.
 * Initial firmware software clock bookkeeping is 48 MHz; not measured hardware.
 */
#define NOVA_ORIGINAL_NOMINAL_CLOCK_HZ UINT32_C(48000000)

void nova_original_clock_setup(void);
void nova_original_domain_select(uint32_t value);
/* Original EA20(4,0), using the actual factory word at10000234. Delay callbacks
 * take original units; long delay returns nonzero on success. No trim constant
 * is guessed. Caller must reject unsupported effective frequencies or adapt
 * its timing; the existing research delay implementation assumes48MHz.
 */
bool nova_original_clock_calibrate_4_0(void (*delay_units)(uint32_t),
                                     int (*delay_long)(uint32_t));
uint32_t nova_original_clock_source_hz(void);
uint32_t nova_original_clock_effective_hz(void);
uint32_t nova_original_clock_factory_word(void);
/* Original APP4A9C(-1) / BOOT5D0(-1) enable path. Returns the final15038
 * sample; the original application caller ignored it, including zero timeout.
 * Counter100 produces at most101 reads. No peripheral role is guessed.
 */
uint32_t nova_original_shared_startup_enable(void (*delay_units)(uint32_t),
                                            int (*delay_long)(uint32_t));
/* delay callback receives ORIGINAL routine 0xdde8 argument units. */
bool nova_original_gate_write(uint32_t mask, bool enable,
                              void (*original_delay_units)(uint32_t));
