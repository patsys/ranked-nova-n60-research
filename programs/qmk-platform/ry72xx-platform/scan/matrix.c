// Copyright 2026 patsys
// SPDX-License-Identifier: GPL-3.0-or-later

/* QMK CUSTOM_MATRIX=lite integration, backed by original analog acquisition.
 * Requires the matching platform's real delay implementation. No weak fallback. */
#include "matrix.h"
#include "nova_acquisition.h"

extern void             nova_platform_delay_original_units(uint32_t units);
extern int              nova_platform_delay_original_long(uint32_t units);
static nova_acquisition acquisition;
#ifdef NOVA_USB_DIAGNOSTIC
/* Snapshot existing main-loop acquisition state; no peripheral reads/writes.
 * Only the diagnostic VIA query calls this, after matrix scanning completes. */
bool nova_matrix_diagnostic(unsigned bank, uint16_t samples[RANKED_CHANNELS], uint16_t *row) {
    if (bank >= RANKED_BANKS || !samples || !row) return false;
    for (unsigned channel = 0; channel < RANKED_CHANNELS; ++channel)
        samples[channel] = acquisition.samples[bank][channel];
    uint16_t rows[RANKED_BANKS];
    nova_acquisition_rows(&acquisition, rows);
    *row = rows[bank];
    return acquisition.initialized;
}
#endif
volatile bool nova_matrix_initialization_failed;
static void   original_delay(uint32_t units, void *context) {
    (void)context;
    nova_platform_delay_original_units(units);
}
static bool original_settle(uint32_t units, void *context) {
    (void)context;
    return nova_platform_delay_original_long(units) != 0;
}
void matrix_init_custom(void) {
    const nova_scan_io io = {
        .read32               = nova_scan_mmio_read32,
        .write32              = nova_scan_mmio_write32,
        .delay_original_units = original_delay,
        .context              = 0,
    };
    nova_matrix_initialization_failed = !nova_acquisition_init_settled(&acquisition, &io, original_settle);
}
bool matrix_scan_custom(matrix_row_t current_matrix[]) {
    if (!nova_acquisition_scan(&acquisition)) return false;
    uint16_t rows[RANKED_BANKS];
    nova_acquisition_rows(&acquisition, rows);
    bool changed = false;
    for (unsigned bank = 0; bank < RANKED_BANKS; ++bank) {
        if (current_matrix[bank] != rows[bank]) changed = true;
        current_matrix[bank] = rows[bank];
    }
    return changed;
}
