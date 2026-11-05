/* Offline startup test fixture; this is not the keyboard application. */
#include <stdint.h>
volatile uint32_t nova_test_initialized = 0x12345678;
volatile uint32_t nova_test_zero[7];
int main(void) {
    for (;;) { nova_test_zero[0] = nova_test_initialized; }
}
