// Copyright 2026 patsys
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once
#include <stdint.h>
void wait_us(uint32_t us);
void wait_ms(uint32_t ms);
/* Generic digital-matrix helper; analog acquisition uses recovered delays. */
static inline void waitInputPinDelay(void) {
    wait_us(1);
}
