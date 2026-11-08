/* Offline emulator entry points only; never part of runtime firmware. */
#include "nova_acquisition.h"
nova_acquisition nova_test_state;
uint32_t nova_test_initial_bits;
uint16_t nova_test_rows[RANKED_BANKS];
__attribute__((noinline)) void nova_test_delay(uint32_t units, void *context) {
    (void)units; (void)context;
    __asm__ volatile("nop"); /* Emulator intercepts this function entry. */
}
static void setup(void) {
    nova_test_state.io.read32 = nova_scan_mmio_read32;
    nova_test_state.io.write32 = nova_scan_mmio_write32;
    nova_test_state.io.delay_original_units = nova_test_delay;
    nova_test_state.io.context = 0;
}
void nova_test_init(void) {
    const nova_scan_io io = {nova_scan_mmio_read32, nova_scan_mmio_write32, nova_test_delay, 0};
    (void)nova_acquisition_init(&nova_test_state, &io);
}
void nova_test_scan(void) {
    setup();
    nova_test_state.initialized = true;
    for (unsigned i = 0; i < RANKED_CHANNELS; ++i)
        nova_test_state.channel_bank_bits[i] = (uint16_t)nova_test_initial_bits;
    (void)nova_acquisition_scan(&nova_test_state);
    nova_acquisition_rows(&nova_test_state, nova_test_rows);
}
