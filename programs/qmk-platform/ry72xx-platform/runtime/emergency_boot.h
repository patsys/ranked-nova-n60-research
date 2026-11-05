// Copyright 2026 patsys
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once
#include <stdbool.h>
#include <stdint.h>
enum { NOVA_EMERGENCY_DISABLED = 0, NOVA_EMERGENCY_ANY_KEY = 1, NOVA_EMERGENCY_ESC = 2 };
#ifndef NOVA_EMERGENCY_READINESS_ATTEMPTS
#    define NOVA_EMERGENCY_READINESS_ATTEMPTS 100
#endif
#ifndef NOVA_EMERGENCY_RETRY_LONG_UNITS
#    define NOVA_EMERGENCY_RETRY_LONG_UNITS 1
#endif
#if NOVA_EMERGENCY_READINESS_ATTEMPTS < 1 || NOVA_EMERGENCY_READINESS_ATTEMPTS > 1000
#    error Emergency readiness attempts must be bounded between 1 and 1000
#endif
#if NOVA_EMERGENCY_RETRY_LONG_UNITS < 1 || NOVA_EMERGENCY_RETRY_LONG_UNITS > 0x01ffffff
#    error Emergency retry original long-delay argument is invalid
#endif
bool                           nova_emergency_hold_detected(unsigned mode, uint8_t required_scans);
bool                           nova_emergency_boot_requested(void);
__attribute__((noreturn)) void mcu_reset(void);
__attribute__((noreturn)) void bootloader_jump(void);
__attribute__((noreturn)) void nova_runtime_halt(void);
