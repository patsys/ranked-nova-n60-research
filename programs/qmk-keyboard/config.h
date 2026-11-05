// Copyright 2026 patsys
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once
#define MATRIX_ROWS 6
#define MATRIX_COLS 11
#define NOVA_SCAN_CONVERSION_SETTLE_UNITS 20
#define NOVA_EMERGENCY_HOLD_MODE 2
#define NOVA_EMERGENCY_HOLD_SCANS 3

#ifdef RGB_MATRIX_ENABLE
#    define RGB_MATRIX_LED_COUNT 62
#    define RGB_MATRIX_LED_FLUSH_LIMIT 16
#endif
