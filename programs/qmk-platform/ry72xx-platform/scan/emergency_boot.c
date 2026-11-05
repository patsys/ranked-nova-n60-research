// Copyright 2026 patsys
// SPDX-License-Identifier: GPL-3.0-or-later

#include "emergency_boot.h"
#include "matrix.h"
#include "recovered_scan.h"
extern int  nova_platform_delay_original_long(uint32_t units);
extern bool matrix_scan_custom(matrix_row_t current_matrix[]);

/* Calling the custom acquisition directly avoids the ordinary QMK debounce
 * timer while interrupts are still masked during early initialization.
 * The recovered analog hysteresis (>30 press,<20 release) remains in use.
 * Empty/unsettled batches restart the hold counter instead of abandoning the
 * entire startup check. This is a bounded readiness window, not measured ms.
 */
bool nova_emergency_hold_detected(unsigned mode, uint8_t required_scans) {
    if ((mode != NOVA_EMERGENCY_ANY_KEY && mode != NOVA_EMERGENCY_ESC) || required_scans == 0) return false;
    if (required_scans > NOVA_EMERGENCY_READINESS_ATTEMPTS) return false;
    matrix_row_t allowed[MATRIX_ROWS] = {0};
    matrix_row_t stable[MATRIX_ROWS]  = {0};
    matrix_row_t raw[MATRIX_ROWS]     = {0};
    for (unsigned row = 0; row < MATRIX_ROWS; ++row) {
        for (unsigned col = 0; col < MATRIX_COLS; ++col) {
            if (ranked_position_present(row, col) && (mode == NOVA_EMERGENCY_ANY_KEY || (row == 0 && col == 0))) allowed[row] |= (matrix_row_t)1u << col;
        }
    }
    uint8_t consecutive = 0;
    for (unsigned attempt = 0; attempt < NOVA_EMERGENCY_READINESS_ATTEMPTS; ++attempt) {
        (void)matrix_scan_custom(raw);
        bool held = false;
        for (unsigned row = 0; row < MATRIX_ROWS; ++row) {
            stable[row] &= raw[row] & allowed[row];
            held |= stable[row] != 0;
        }
        if (held) {
            ++consecutive;
        } else {
            /* No previous candidate survived this batch. Start a new hold
             * using only currently observed, permitted populated positions. */
            bool current_held = false;
            for (unsigned row = 0; row < MATRIX_ROWS; ++row) {
                stable[row] = raw[row] & allowed[row];
                current_held |= stable[row] != 0;
            }
            consecutive = current_held ? 1 : 0;
        }
        if (consecutive >= required_scans) return true;
        if (attempt + 1u < NOVA_EMERGENCY_READINESS_ATTEMPTS && !nova_platform_delay_original_long(NOVA_EMERGENCY_RETRY_LONG_UNITS)) return false;
    }
    return false;
}

bool nova_emergency_boot_requested(void) {
    return nova_emergency_hold_detected(NOVA_EMERGENCY_HOLD_MODE, NOVA_EMERGENCY_HOLD_SCANS);
}
