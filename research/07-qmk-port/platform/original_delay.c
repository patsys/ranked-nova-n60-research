#include <stdint.h>

extern void nova_delay48_loop(uint32_t count);

/* Original0xdde8 zero guard plus the selected nominal48MHz helper. Platform
 * must keep the corresponding clock setup; do not label these microseconds.
 */
void nova_platform_delay_original_units(uint32_t count) {
    if (count != 0) nova_delay48_loop(count);
}

/* Original0xdd80 call sequence, including its initial count<<7 call followed
 * by count calls with999. Positive count must be <=0x01ffffff to prevent the
 * original32bit shift becoming zero and underflowing the raw delay loop.
 */
int nova_platform_delay_original_long(uint32_t count) {
    if (count == 0) return 1;
    if (count > UINT32_C(0x01ffffff)) return 0;
    nova_delay48_loop(count << 7);
    do {
        nova_delay48_loop(999);
    } while (--count != 0);
    return 1;
}
