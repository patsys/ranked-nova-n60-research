#ifdef VIA_ENABLE
#include "via.h"
#include "raw_hid.h"
#ifdef NOVA_USB_DIAGNOSTIC
#include "matrix.h"
extern bool nova_matrix_diagnostic(unsigned bank, uint16_t samples[11], uint16_t *row);
#endif

/* Upstream buffer commands document a28-byte maximum but trust the packet's
 * size byte. Reject oversized requests before the actual VIA handler sees them.
 */
bool via_command_kb(uint8_t *data, uint8_t length) {
    if (length != 32) return true;
#if defined(NOVA_USB_DIAGNOSTIC) && defined(RGB_MATRIX_ENABLE)
    if (data[0] == id_get_keyboard_value && data[1] == 0x81) {
        extern void nova_rgb_diagnostic(uint8_t *data);
        for (unsigned i=3;i<32;++i) data[i]=0;
        nova_rgb_diagnostic(data+3);
        raw_hid_send(data,length);
        return true;
    }
#endif
#ifdef NOVA_USB_DIAGNOSTIC
    /* Research-only GET keyboard value 0x80: explicit read-only snapshot.
     * [2,0x80,bank] -> version/status/raw row, 11 big-endian samples,
     * debounced row. Invalid banks return status 0xff and zero data.
     * Does not enable VIA_INSECURE or expose arbitrary memory/MMIO access.
     */
    if (data[0] == id_get_keyboard_value && data[1] == 0x80) {
        const uint8_t bank = data[2];
        for (unsigned i = 3; i < 32; ++i) data[i] = 0;
        data[3] = 1;
        data[4] = 0xff;
        if (bank < MATRIX_ROWS) {
            uint16_t samples[11], row = 0;
            data[4] = nova_matrix_diagnostic(bank, samples, &row) ? 1 : 0;
            data[6] = row >> 8; data[7] = row;
            for (unsigned i = 0; i < 11; ++i) {
                data[8+2*i] = samples[i] >> 8;
                data[9+2*i] = samples[i];
            }
            row = matrix_get_row(bank);
            data[30] = row >> 8; data[31] = row;
        }
        raw_hid_send(data, length);
        return true;
    }
#endif
    switch (data[0]) {
        case id_dynamic_keymap_macro_get_buffer:
        case id_dynamic_keymap_macro_set_buffer:
        case id_dynamic_keymap_get_buffer:
        case id_dynamic_keymap_set_buffer:
            if (data[3] > 28) {
                data[0]=id_unhandled;
                raw_hid_send(data,length);
                return true;
            }
            break;
    }
    return false;
}
#endif
