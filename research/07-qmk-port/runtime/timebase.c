#include <stdint.h>
#include "timer.h"
#include "../platform/recovered_clock.h"
#include "emergency_boot.h"
#include "usb_diagnostic.h"

#define REG32(a) (*(volatile uint32_t *)(uintptr_t)(a))
volatile uint32_t timer_count;
static uint32_t saved_timer;

void SysTick_Handler(void) { ++timer_count; nova_usb_diagnostic_systick(); }

/* Standard ARM SysTick, core clock source. Uses the original nominal clock
 * bookkeeping; actual clock frequency has not been measured on hardware.
 * Custom polling acquisition replaces the proprietary SysTick scan callbacks.
 */
void timer_init(void) {
    REG32(0xe000e010u) = 0;
    timer_count = 0;
    REG32(0xe000e014u) = NOVA_ORIGINAL_NOMINAL_CLOCK_HZ / 1000u - 1u;
    REG32(0xe000e018u) = 0;
#ifdef NOVA_USB_DIAGNOSTIC
    /* Priority0 preempts the USB IRQ's priority1, including an IRQ storm.
     * Preserve the neighboring SHPR3 bytes; never reset the deadline here. */
    REG32(0xe000ed20u) &= UINT32_C(0x00ffffff);
#endif
    REG32(0xe000e010u) = 7; /* ENABLE | TICKINT | CLKSOURCE */
}
void timer_clear(void) { timer_count = 0; }
void timer_save(void) { saved_timer = timer_count; }
void timer_restore(void) { timer_count = saved_timer; }
uint16_t timer_read(void) { return (uint16_t)timer_count; }
uint32_t timer_read32(void) { return timer_count; }

void wait_ms(uint32_t duration) {
    uint32_t start = timer_count;
    while ((uint32_t)(timer_count - start) < duration) {
        __asm__ volatile("nop");
    }
}
/* Microsecond waits use live SysTick countdown rather than treating recovered
 * delay arguments as microseconds. Interrupts/timer must already be running.
 * Sampling more slowly than a full SysTick period only extends a wait.
 */
void wait_us(uint32_t duration) {
    while (duration != 0) {
        uint32_t chunk = duration > 500u ? 500u : duration;
        uint32_t needed = chunk * (NOVA_ORIGINAL_NOMINAL_CLOCK_HZ / 1000000u);
        uint32_t period = REG32(0xe000e014u) + 1u;
        uint32_t previous = REG32(0xe000e018u);
        while (needed != 0) {
            uint32_t current = REG32(0xe000e018u);
            uint32_t elapsed = previous >= current ? previous - current : previous + period - current;
            needed = elapsed >= needed ? 0 : needed - elapsed;
            previous = current;
        }
        duration -= chunk;
    }
}

__attribute__((noreturn)) void nova_runtime_halt(void) {
    __asm__ volatile("cpsid i" ::: "memory");
    for (;;) __asm__ volatile("wfe");
}

/* Original application uses this retained request + ARM SYSRESETREQ sequence.
 * It requests the preserved bootloader, not an EEPROM/flash erase operation.
 */
__attribute__((noreturn)) void mcu_reset(void) {
    __asm__ volatile("cpsid i\ndsb" ::: "memory");
    REG32(0xe000ed0cu) = 0x05fa0004u;
    __asm__ volatile("dsb" ::: "memory");
    for (;;) __asm__ volatile("wfe");
}
__attribute__((noreturn)) void bootloader_jump(void) {
    __asm__ volatile("cpsid i" ::: "memory");
    REG32(0x4001400cu) = 0x5ac396c5u;
    mcu_reset();
}
