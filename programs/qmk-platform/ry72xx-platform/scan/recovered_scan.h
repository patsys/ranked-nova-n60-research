// Copyright 2026 patsys
// SPDX-License-Identifier: GPL-3.0-or-later

/* Evidence-backed pure scan helpers, not a complete QMK hardware driver. */
#pragma once
#include <stdint.h>
#include <stdbool.h>

enum { RANKED_BANKS = 6, RANKED_CHANNELS = 11, RANKED_ABSENT_ID = 1 };
extern const uint8_t   ranked_bank_pin_codes[RANKED_BANKS];
extern const uint8_t   ranked_channel_pin_codes[RANKED_CHANNELS];
extern const uint8_t   ranked_original_key_ids[RANKED_CHANNELS][RANKED_BANKS];
extern const uintptr_t ranked_pin_config_bases[4];

/* Literal behavior recovered from 0x4d3e..0x4d68; not a configurable Hall model. */
uint16_t  ranked_observed_hysteresis(uint16_t bank_bits, unsigned bank, uint16_t sample);
bool      ranked_position_present(unsigned bank, unsigned channel);
uintptr_t ranked_result_address(unsigned channel);
uintptr_t ranked_pin_config_address(uint8_t encoded_pin);
uintptr_t ranked_pin_write10_address(uint8_t encoded_pin);
uintptr_t ranked_pin_write20_address(uint8_t encoded_pin);
uint32_t  ranked_pin_mask(uint8_t encoded_pin);
/* Exact arithmetic at 0xeaec; caller must validate SysTick range/clock source. */
uint32_t ranked_observed_systick_reload(uint32_t nominal_clock_hz, uint32_t period_argument);

/* These functions perform no MMIO. A future platform must provide verified
 * clock/reset, acquisition startup, timing, USB, and matrix/event integration.
 * GPIO identifiers are encoded IDs, not chip-package pin numbers. */
