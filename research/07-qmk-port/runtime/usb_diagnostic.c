#include "usb_diagnostic.h"
#ifdef NOVA_USB_DIAGNOSTIC
#include "emergency_boot.h"
#include <stddef.h>

#define TRACE ((volatile nova_usb_diagnostic_trace *)(uintptr_t)NOVA_DIAG_TRACE_ADDRESS)
static uint32_t primask(void) { uint32_t v; __asm__ volatile("mrs %0, primask":"=r"(v)); return v; }
static uint32_t ipsr(void) { uint32_t v; __asm__ volatile("mrs %0, ipsr":"=r"(v)); return v; }

void nova_usb_diagnostic_init(void) {
    uint32_t sequence = 1;
    if (TRACE->magic==NOVA_DIAG_TRACE_MAGIC && TRACE->version==NOVA_DIAG_TRACE_VERSION &&
        TRACE->byte_length==sizeof(*TRACE)) sequence=TRACE->boot_sequence+1u;
    volatile uint32_t *p=(volatile uint32_t *)TRACE;
    for (unsigned i=0;i<sizeof(*TRACE)/sizeof(uint32_t);++i) p[i]=0;
    TRACE->version=NOVA_DIAG_TRACE_VERSION;TRACE->byte_length=sizeof(*TRACE);
    TRACE->boot_sequence=sequence;TRACE->stage=NOVA_DIAG_STAGE_START;
    TRACE->deadline_ticks=NOVA_DIAG_DEADLINE_TICKS;
    TRACE->magic=NOVA_DIAG_TRACE_MAGIC;
}
void nova_usb_diagnostic_mark(uint32_t stage) { TRACE->stage=stage; }
void nova_usb_diagnostic_arm(void) { TRACE->ticks=0;TRACE->armed=1; }
void nova_usb_diagnostic_systick(void) {
    uint32_t elapsed=TRACE->ticks+1u;TRACE->ticks=elapsed;
    /* Absolute deadline from arm: USB reset/configuration callbacks NEVER
     * restart it. A lost configuration after the deadline also returns boot.
     */
    if (TRACE->armed && elapsed>=TRACE->deadline_ticks && TRACE->current_configuration==0)
        nova_usb_diagnostic_boot_request(NOVA_DIAG_REASON_USB_TIMEOUT);
}
void nova_usb_diagnostic_irq(bool entering) {
    if (entering) ++TRACE->irq_entries; else ++TRACE->irq_exits;
}
void nova_usb_diagnostic_status(uint32_t value) { TRACE->last_status=value;++TRACE->status_reads; }
void nova_usb_diagnostic_event(uint32_t value) {
    TRACE->last_event=value;++TRACE->event_reads;
    if (value<29u) ++TRACE->event_counts[value];
}
/* V2 reserves words45..47 for shared startup and preexisting AUX reads. */
void nova_usb_diagnostic_shared_startup(uint32_t value) { TRACE->event_counts[29]=value; }
void nova_usb_diagnostic_aux(uint32_t value) {
    ++TRACE->event_counts[30];TRACE->event_counts[31]=value;
}
void nova_usb_diagnostic_configured(uint32_t value) {
    TRACE->current_configuration=value;
    if (value) TRACE->ever_configured=1;
    ++TRACE->configuration_changes;
}
__attribute__((noreturn)) void nova_usb_diagnostic_boot_request(uint32_t reason) {
    uint32_t previous_mask=primask(),exception=ipsr();
    __asm__ volatile("cpsid i" ::: "memory");
    TRACE->stage_at_boot_request=TRACE->stage;TRACE->stage=NOVA_DIAG_STAGE_BOOT_REQUEST;
    TRACE->boot_reason=reason;TRACE->primask_on_request=previous_mask;TRACE->ipsr_on_request=exception;
    TRACE->armed=0;
    bootloader_jump();
}

/* Both original-used RAM windows are word readable. Reject all other frame
 * pointers rather than risk a second fault from an arbitrary exception SP.
 */
__attribute__((noreturn)) void nova_usb_diagnostic_fault(const uint32_t *frame,
                                                       uint32_t exception_return,
                                                       uint32_t exception_number) {
    uintptr_t address=(uintptr_t)frame;
    uint32_t captured[8];
    bool valid=(address&3u)==0 &&
        ((address>=UINT32_C(0x20000000) && address<=UINT32_C(0x20001c50)-32u) ||
         (address>=UINT32_C(0x20003000) && address<=UINT32_C(0x200031b4)-32u &&
          /* A nested exception's frame in our new fault stack may have been
           * overwritten by this C prologue. Do not report it as trustworthy. */
          !(address<UINT32_C(0x200031b0) && address+32u>UINT32_C(0x20003100))));
    for (unsigned i=0;i<8;++i) captured[i]=valid?frame[i]:UINT32_C(0xffffffff);
    if (TRACE->magic!=NOVA_DIAG_TRACE_MAGIC || TRACE->version!=NOVA_DIAG_TRACE_VERSION ||
        TRACE->byte_length!=sizeof(*TRACE)) nova_usb_diagnostic_init();
    TRACE->exception_number=exception_number;TRACE->exception_return=exception_return;
    TRACE->exception_sp=(uint32_t)address;
    for (unsigned i=0;i<8;++i) TRACE->stacked_frame[i]=captured[i];
    nova_usb_diagnostic_boot_request(exception_number==2?NOVA_DIAG_REASON_NMI:NOVA_DIAG_REASON_HARDFAULT);
}

/* Original bootloader's forwarder preserves EXC_RETURN in LR. Obtain the
 * hardware frame before switching MSP to the separate original-used upper RAM
 * window, so reset reporting does not depend on the potentially damaged stack.
 * These handlers never return or attempt exception-frame restoration.
 */
#define FAULT_ENTRY(number) \
    __asm__ volatile("mov r1, lr\nmovs r2, #4\ntst r1, r2\nbeq 1f\n" \
                     "mrs r0, psp\nb 2f\n1: mrs r0, msp\n2:\n" \
                     "ldr r3, =0x200031b0\nmsr msp, r3\nmovs r2, #" #number "\n" \
                     "b nova_usb_diagnostic_fault\n")
__attribute__((naked,noreturn)) void HardFault_Handler(void) { FAULT_ENTRY(3); }
__attribute__((naked,noreturn)) void NMI_Handler(void) { FAULT_ENTRY(2); }
#endif
