#include "recovered_scan.h"

/* Original literal tables 0xf61a, 0xf620, 0xf660. */
const uint8_t ranked_bank_pin_codes[RANKED_BANKS] = {24, 23, 22, 21, 20, 19};
const uint8_t ranked_channel_pin_codes[RANKED_CHANNELS] = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10};
const uint8_t ranked_original_key_ids[RANKED_CHANNELS][RANKED_BANKS] = {
    {21, 42, 63, 84, 105, 1},
    {22, 43, 64, 85, 106, 32},
    {23, 44, 65, 86, 107, 33},
    {24, 45, 66, 87, 111, 34},
    {25, 46, 67, 88, 115, 53},
    {26, 47, 68, 89, 116, 54},
    {27, 48, 69, 90, 117, 1},
    {28, 49, 70, 91, 118, 74},
    {29, 50, 71, 92, 95, 75},
    {30, 51, 72, 93, 1, 76},
    {31, 52, 73, 94, 97, 1},
};
/* Decoded by executing original scatter-load decompressor. */
const uintptr_t ranked_pin_config_bases[4] = {0x40018090u, 0x40018148u, 0x4001810cu, 0x4001812cu};

uint16_t ranked_observed_hysteresis(uint16_t bank_bits, unsigned bank, uint16_t sample) {
    if (bank >= RANKED_BANKS) return bank_bits;
    const uint16_t bit = (uint16_t)(1u << bank);
    if (sample > 30u) return (uint16_t)(bank_bits | bit);
    if (sample < 20u) return (uint16_t)(bank_bits & (uint16_t)~bit);
    return bank_bits;
}
bool ranked_position_present(unsigned bank, unsigned channel) {
    return bank < RANKED_BANKS && channel < RANKED_CHANNELS &&
           ranked_original_key_ids[channel][bank] != RANKED_ABSENT_ID;
}
uintptr_t ranked_result_address(unsigned channel) {
    return channel < RANKED_CHANNELS ? 0x4000e09cu + 4u * channel : 0;
}
uintptr_t ranked_pin_config_address(uint8_t pin) {
    const unsigned group = (pin >> 5) & 3u;
    return group == 1u ? 0 : ranked_pin_config_bases[group] + 4u * (pin & 31u);
}
uintptr_t ranked_pin_write10_address(uint8_t pin) {
    return 0x40018010u + 4u * ((pin >> 5) & 3u);
}
uintptr_t ranked_pin_write20_address(uint8_t pin) {
    return 0x40018020u + 4u * ((pin >> 5) & 3u);
}
uint32_t ranked_pin_mask(uint8_t pin) { return (uint32_t)1u << (pin & 31u); }
uint32_t ranked_observed_systick_reload(uint32_t nominal_clock_hz, uint32_t period_argument) {
    return (nominal_clock_hz / 1000000u) * period_argument - 16u;
}
