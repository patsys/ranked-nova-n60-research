// Copyright 2026 patsys
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once
/* Research ARMv6-M baseline, not a manufacturer/part identification.
 * 22 native external IRQ vector entries were recovered; ChibiOS requires
 * rounding its table size to a multiple of eight. Entries22/23 are unused.
 * Cortex-M0 has two implemented priority bits. Confirm physical core before use.
 */
#define CORTEX_MODEL 0
#define CORTEX_HAS_FPU 0
#define CORTEX_PRIORITY_BITS 2U
#define CORTEX_NUM_VECTORS 24
#define CORTEX_MPU_REGIONS 0
