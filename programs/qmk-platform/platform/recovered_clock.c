#include "recovered_clock.h"
#include <stddef.h>

/* Override for an offline register model. Names deliberately avoid guessed
 * vendor register fields; every volatile operation follows original code.
 */
#ifndef NOVA_REG32
#define NOVA_REG32(address) (*(volatile uint32_t *)(uintptr_t)(address))
#endif

/* Relocated counterpart of original RAM bookkeeping at20000428. Fixed native
 * RAM addresses overlap the new application's stacks and MUST NOT be reused.
 * Original field08/0c are retained without assigning unproven semantics.
 */
static volatile struct {
    uint32_t source_hz;
    uint32_t effective_hz;
    uint32_t field_08;
    uint32_t field_0c;
    uint32_t factory_word;
} nova_clock_state = {NOVA_ORIGINAL_NOMINAL_CLOCK_HZ,
                      NOVA_ORIGINAL_NOMINAL_CLOCK_HZ, 0x2000, 0x2000, 0};

uint32_t nova_original_clock_source_hz(void) { return nova_clock_state.source_hz; }
uint32_t nova_original_clock_effective_hz(void) { return nova_clock_state.effective_hz; }
uint32_t nova_original_clock_factory_word(void) { return nova_clock_state.factory_word; }

uint32_t nova_original_shared_startup_enable(void (*delay_units)(uint32_t),
                                            int (*delay_long)(uint32_t)) {
    if (delay_units == NULL || delay_long == NULL) return 0;
    (void)nova_original_gate_write(UINT32_C(0x80000), true, delay_units);
    (void)delay_long(10);
    NOVA_REG32(0x40015000u) = 1;
    uint32_t status = 0;
    for (unsigned attempt=0;attempt<=100u;++attempt) {
        status=NOVA_REG32(0x40015038u);
        if (status != 0) break;
    }
    return status;
}

/* Original EA20 with fixed arguments(4,0), including EAB4 and F3A8. This is
 * deliberately not a generic frequency-selection API. Repeated factory reads
 * preserve the observed original operation order; no factory contents assumed.
 */
bool nova_original_clock_calibrate_4_0(void (*delay_units)(uint32_t),
                                     int (*delay_long)(uint32_t)) {
    if (delay_units == NULL || delay_long == NULL) return false;
    nova_clock_state.field_08 = 0x2000;
    nova_clock_state.field_0c = 0x2000;
    uint32_t value = NOVA_REG32(0x4001900cu) & ~UINT32_C(0x700);
    value |= (NOVA_REG32(0x10000234u) & UINT32_C(0x70)) << 4;
    NOVA_REG32(0x4001900cu) = value;
    delay_units(10);
    value = (NOVA_REG32(0x10000234u) << 8) >> 24;
    value |= (NOVA_REG32(0x10000234u) >> 8) & UINT32_C(0xf0000);
    NOVA_REG32(0x40019010u) = value;
    if (!delay_long(1)) return false;
    value = NOVA_REG32(0x10000234u);
    nova_clock_state.factory_word = value;
    /* ARM32 (word<<25)>>29 extracts bits4..6, including bit6. */
    nova_clock_state.source_hz = UINT32_C(24000000) +
                                UINT32_C(4000000) * ((value << 25) >> 29);
    NOVA_REG32(0x40014018u) = 0; /* EAB4 divisor argument0. */
    nova_clock_state.effective_hz = nova_clock_state.source_hz;
    /* F3A8 ->2BA8: SysTick priority2, external IRQ2 priority3, IRQ4 priority1.
     * Two implemented priority bits occupy the high two bits of each byte.
     */
    NOVA_REG32(0xe000ed20u) = (NOVA_REG32(0xe000ed20u) & ~UINT32_C(0xff000000)) | UINT32_C(0x80000000);
    NOVA_REG32(0xe000e400u) = (NOVA_REG32(0xe000e400u) & ~UINT32_C(0x00ff0000)) | UINT32_C(0x00c00000);
    NOVA_REG32(0xe000e404u) = (NOVA_REG32(0xe000e404u) & ~UINT32_C(0xff)) | UINT32_C(0x40);
    return true;
}

/* Original 0xd5f0. Preserve order: repeated writes may have side effects. */
void nova_original_clock_setup(void) {
    NOVA_REG32(0x40014028u) = 0;
    NOVA_REG32(0x40014060u) = (NOVA_REG32(0x40014060u) & ~2u) | 2u;
    NOVA_REG32(0x40014050u) = NOVA_REG32(0x40014050u) | 0x01000000u;
    NOVA_REG32(0x4001404cu) = 0;
    NOVA_REG32(0x40014050u) = (NOVA_REG32(0x40014050u) & ~0x1fu) | 0x11u;
    NOVA_REG32(0x40014050u) = NOVA_REG32(0x40014050u) | 0x01000000u;
    NOVA_REG32(0x40014050u) = (NOVA_REG32(0x40014050u) & ~0xe0u) | 0x40u;
    NOVA_REG32(0x40014050u) = (NOVA_REG32(0x40014050u) & ~0x1f00u) | 0x1100u;
    NOVA_REG32(0x40014050u) = NOVA_REG32(0x40014050u) | 0x01000000u;
    NOVA_REG32(0x40014050u) = (NOVA_REG32(0x40014050u) & ~0xe000u) | 0x4000u;
}

/* Original 0xd57c; (0x40014040 << 18) modulo 2^32 is 0x01000000. */
void nova_original_domain_select(uint32_t value) {
    NOVA_REG32(0x40014050u) = NOVA_REG32(0x40014050u) | 0x01000000u;
    NOVA_REG32(0x4001404cu) = value;
}

/* Original 0xd524. A caller must supply the calibrated delay implementation;
 * this file intentionally supplies no guessed timing or silent no-op delay.
 */
bool nova_original_gate_write(uint32_t mask, bool enable,
                              void (*original_delay_units)(uint32_t)) {
    if (original_delay_units == NULL) return false;
    if (enable) NOVA_REG32(0x4001402cu) = mask;
    else NOVA_REG32(0x40014030u) = mask;
    original_delay_units(10);
    return true;
}
