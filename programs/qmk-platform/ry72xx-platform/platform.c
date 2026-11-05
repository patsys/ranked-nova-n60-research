// Copyright 2026 patsys
// SPDX-License-Identifier: GPL-3.0-or-later

#include <stdbool.h>
#include <stdint.h>
#include "keyboard.h"
#include "recovered_clock.h"
#include "emergency_boot.h"
#include "usb_diagnostic.h"
#ifdef RGB_MATRIX_ENABLE
#    include "rgb_matrix.h"
#endif
extern bool          nova_usb_keyboard_init(void);
extern void          nova_usb_keyboard_pre_task(void);
extern bool          nova_usb_keyboard_suspended(void);
extern void          nova_usb_keyboard_suspend_task(void);
extern void          nova_usb_keyboard_task(void);
extern volatile bool nova_matrix_initialization_failed;
extern void          nova_platform_delay_original_units(uint32_t);
extern int           nova_platform_delay_original_long(uint32_t);
volatile unsigned    nova_runtime_failure;
void                 platform_setup(void) {
    __asm__ volatile("cpsid i" ::: "memory");
    nova_usb_diagnostic_init();
    /* Clear inherited enabled/pending external IRQs before initializing ours. */
    *(volatile uint32_t *)0xe000e180u = 0xffffffffu;
    *(volatile uint32_t *)0xe000e280u = 0xffffffffu;
    nova_usb_diagnostic_mark(NOVA_DIAG_STAGE_CLOCK_SETUP);
    nova_original_clock_setup();
    nova_usb_diagnostic_mark(NOVA_DIAG_STAGE_CLOCK_FACTORY);
    if (!nova_original_clock_calibrate_4_0(nova_platform_delay_original_units, nova_platform_delay_original_long)) {
        nova_runtime_failure = 3;
        nova_usb_diagnostic_boot_request(NOVA_DIAG_REASON_CLOCK_INIT);
    }
    /* Delay helpers and SysTick currently assume this one recovered frequency.
     * Fail to the preserved bootloader instead of proceeding at a guessed rate. */
    if (nova_original_clock_effective_hz() != NOVA_ORIGINAL_NOMINAL_CLOCK_HZ) {
        nova_runtime_failure = 4;
        nova_usb_diagnostic_boot_request(NOVA_DIAG_REASON_CLOCK_RATE);
    }
}
void protocol_setup(void) {}
void protocol_pre_init(void) {
    // QMK initializes SysTick at the start of keyboard_init(). Bootmagic and
    // other standard initialization hooks may wait on that timer. External
    // IRQs were cleared during platform_setup; USB IRQ4 is enabled only after
    // its device state is initialized in protocol_post_init().
    __asm__ volatile("cpsie i" ::: "memory");
}
void protocol_post_init(void) {
    if (nova_matrix_initialization_failed) {
        nova_runtime_failure = 1;
        nova_usb_diagnostic_boot_request(NOVA_DIAG_REASON_MATRIX_INIT);
    }
    nova_usb_diagnostic_mark(NOVA_DIAG_STAGE_EMERGENCY_CHECK);
    if (nova_emergency_boot_requested()) nova_usb_diagnostic_boot_request(NOVA_DIAG_REASON_EMERGENCY_KEY);
    nova_usb_diagnostic_mark(NOVA_DIAG_STAGE_SHARED_STARTUP);
    /* Original main ignored the status after this bounded native sequence.
     * Keep that behavior: record it, do not invent a status0 boot decision. */
    nova_usb_diagnostic_shared_startup(nova_original_shared_startup_enable(nova_platform_delay_original_units, nova_platform_delay_original_long));
    nova_usb_diagnostic_mark(NOVA_DIAG_STAGE_USB_INIT);
    if (!nova_usb_keyboard_init()) {
        nova_runtime_failure = 2;
        nova_usb_diagnostic_boot_request(NOVA_DIAG_REASON_USB_INIT);
    }
    nova_usb_diagnostic_mark(NOVA_DIAG_STAGE_IRQ_ENABLE);
    nova_usb_diagnostic_arm();
    __asm__ volatile("cpsie i" ::: "memory");
}
void protocol_pre_task(void) {
    nova_usb_keyboard_pre_task();
}
void protocol_keyboard_task(void) {
    if (nova_usb_keyboard_suspended()) {
        nova_usb_keyboard_suspend_task();
#ifdef RGB_MATRIX_ENABLE
        /* Finish the asynchronous black frame while acquisition is paused. */
        rgb_matrix_task();
#endif
        __asm__ volatile("wfi");
        return;
    }
    keyboard_task();
}
void protocol_post_task(void) {
    nova_usb_keyboard_task();
}
