/* Host-only validation: fake bus callbacks, no physical MMIO. */
#include "ranked_usb_io.h"
#include <assert.h>
#include <stdio.h>

typedef struct { uintptr_t address[65]; uint32_t value[65]; unsigned count; } trace;
static void write32(void *context, uintptr_t address, uint32_t value) {
    trace *t = context;
    assert(t->count < 65);
    t->address[t->count] = address;
    t->value[t->count++] = value;
}
static uint8_t read8(void *context, uintptr_t address) {
    (void)context;
    const uint8_t setup[] = {0x81, 6, 0, 0x22, 1, 0, 0xd3, 0};
    if (address >= 0x40017fa0u && address < 0x40017fc0u) {
        assert((address & 3u) == 0);
        return setup[(address - 0x40017fa0u)/4u];
    }
    if (address >= 0x40017500u && address < 0x40017600u) {
        assert((address & 3u) == 0);
        return (uint8_t)(0x80u + (uint32_t)((address - 0x40017500u)/4u));
    }
    assert(address >= 0x40017b00u && address < 0x40017b20u);
    assert((address & 3u) == 0);
    return (uint8_t)(0x80u + (uint32_t)((address - 0x40017b00u)/4u));
}
int main(void) {
    uint8_t source[64];
    for (unsigned i = 0; i < sizeof source; ++i) source[i] = (uint8_t)(0x80u+i);
    trace t = {{0}, {0}, 0};
    ranked_usb_io io = {&t, read8, write32};
    unsigned cases = 0;
    for (unsigned ep = 0; ep <= RANKED_USB_LAST_ENDPOINT; ++ep) {
        unsigned max = ep == 0 ? 8 : 64;
        for (unsigned n = 0; n <= max; ++n) {
            t.count = 0;
            assert(ranked_usb_fifo_submit(&io, ep, source, n));
            assert(t.count == n + 1);
            for (unsigned i = 0; i < n; ++i) {
                assert(t.address[i] == 0x40017c00u-ep*0x200u+i*4u);
                assert(t.value[i] == source[i]);
            }
            assert(t.address[n] == 0x40017ed4u+ep*8u);
            assert(t.value[n] == n);
            ++cases;
        }
    }
    t.count = 0;
    assert(!ranked_usb_fifo_submit(&io, 6, source, 1));
    assert(!ranked_usb_fifo_submit(&io, 0, source, 9));
    assert(!ranked_usb_fifo_submit(&io, 1, source, 65));
    assert(!ranked_usb_fifo_submit(&io, 1, NULL, 1));
    assert(t.count == 0);
    uint8_t rx[8];
    assert(ranked_usb_ep0_receive(&io, rx, 8));
    for (unsigned i = 0; i < 8; ++i) assert(rx[i] == 0x80u+i);
    assert(!ranked_usb_ep0_receive(&io, rx, 9));
    uint8_t vendor[64];
    assert(ranked_usb_vendor_receive(&io, vendor, sizeof vendor));
    for (unsigned i = 0; i < 64; ++i) assert(vendor[i] == 0x80u+i);
    assert(!ranked_usb_vendor_receive(&io, vendor, 65));
    ranked_usb_setup setup;
    assert(ranked_usb_read_setup(&io, &setup));
    assert(setup.request_type == 0x81 && setup.request == 6);
    assert(setup.value == 0x2200 && setup.index == 1 && setup.length == 211);
    printf("%u valid FIFO submission cases, bounds and RX/SETUP checks passed\n", cases);
    return 0;
}
