/* Test-only caller; no replacement of the actual top-level dispatcher. */
#include "ranked_usb_device.h"
static ranked_usb_device device;
static uint8_t read8(void *context,uintptr_t address) {(void)context;return *(volatile uint8_t *)address;}
static uint32_t read32(void *context,uintptr_t address) {(void)context;return *(volatile uint32_t *)address;}
static void write32(void *context,uintptr_t address,uint32_t value) {(void)context;*(volatile uint32_t *)address=value;}
void irq_wrapper_test(void) {
    device.bus.context=0;device.bus.read8=read8;device.bus.read32=read32;device.bus.write32=write32;
    ranked_usb_device_irq(&device);
}
