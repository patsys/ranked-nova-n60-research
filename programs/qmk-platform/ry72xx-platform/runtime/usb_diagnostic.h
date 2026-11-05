// Copyright 2026 patsys
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once
#include <stdint.h>
#include <stdbool.h>

#define NOVA_DIAG_TRACE_ADDRESS UINT32_C(0x20003000)
#define NOVA_DIAG_TRACE_MAGIC UINT32_C(0x4e554442)
#define NOVA_DIAG_TRACE_VERSION 2u
#define NOVA_DIAG_DEADLINE_TICKS 5000u
#define NOVA_DIAG_FAULT_STACK_TOP UINT32_C(0x200031b0)
typedef struct {
    uint32_t magic, version, byte_length, boot_sequence;
    uint32_t stage, deadline_ticks, ticks, ever_configured;
    uint32_t current_configuration, irq_entries, irq_exits, last_status;
    uint32_t last_event, status_reads, event_reads, configuration_changes;
    uint32_t event_counts[32];
    uint32_t boot_reason, primask_on_request, ipsr_on_request, exception_number;
    uint32_t exception_return, exception_sp, stacked_frame[8];
    uint32_t armed, stage_at_boot_request;
} nova_usb_diagnostic_trace;
_Static_assert(sizeof(nova_usb_diagnostic_trace) == 256, "Diagnostic trace must stay within3000..30ff");

enum { NOVA_DIAG_STAGE_START = 1, NOVA_DIAG_STAGE_CLOCK_SETUP = 2, NOVA_DIAG_STAGE_CLOCK_FACTORY = 3, NOVA_DIAG_STAGE_KEYBOARD_SETUP = 4, NOVA_DIAG_STAGE_KEYBOARD_INIT = 5, NOVA_DIAG_STAGE_EMERGENCY_CHECK = 6, NOVA_DIAG_STAGE_USB_INIT = 7, NOVA_DIAG_STAGE_IRQ_ENABLE = 8, NOVA_DIAG_STAGE_MAIN_LOOP = 9, NOVA_DIAG_STAGE_SHARED_STARTUP = 10, NOVA_DIAG_STAGE_BOOT_REQUEST = 99 };
enum { NOVA_DIAG_REASON_USB_TIMEOUT = 1, NOVA_DIAG_REASON_HARDFAULT = 2, NOVA_DIAG_REASON_NMI = 3, NOVA_DIAG_REASON_CLOCK_INIT = 4, NOVA_DIAG_REASON_CLOCK_RATE = 5, NOVA_DIAG_REASON_MATRIX_INIT = 6, NOVA_DIAG_REASON_EMERGENCY_KEY = 7, NOVA_DIAG_REASON_USB_INIT = 8, NOVA_DIAG_REASON_SHARED_STARTUP = 9 };

#ifdef NOVA_USB_DIAGNOSTIC
void                           nova_usb_diagnostic_init(void);
void                           nova_usb_diagnostic_mark(uint32_t stage);
void                           nova_usb_diagnostic_arm(void);
void                           nova_usb_diagnostic_systick(void);
void                           nova_usb_diagnostic_irq(bool entering);
void                           nova_usb_diagnostic_status(uint32_t value);
void                           nova_usb_diagnostic_event(uint32_t value);
void                           nova_usb_diagnostic_configured(uint32_t value);
void                           nova_usb_diagnostic_aux(uint32_t value);
void                           nova_usb_diagnostic_shared_startup(uint32_t value);
__attribute__((noreturn)) void nova_usb_diagnostic_boot_request(uint32_t reason);
#else
static inline void nova_usb_diagnostic_init(void) {}
static inline void nova_usb_diagnostic_mark(uint32_t stage) {
    (void)stage;
}
static inline void nova_usb_diagnostic_arm(void) {}
static inline void nova_usb_diagnostic_systick(void) {}
static inline void nova_usb_diagnostic_shared_startup(uint32_t value) {
    (void)value;
}
__attribute__((noreturn)) void               bootloader_jump(void);
__attribute__((noreturn)) static inline void nova_usb_diagnostic_boot_request(uint32_t reason) {
    (void)reason;
    bootloader_jump();
}
#endif
