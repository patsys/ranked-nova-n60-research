#include "atomic_util.h"
volatile uint32_t nova_atomic_inside;
static uint32_t mask(void) {
    uint32_t result;
    __asm__ volatile("mrs %0, primask" : "=r"(result));
    return result;
}
uint32_t nova_atomic_normal(void) {
    ATOMIC_BLOCK_RESTORESTATE { nova_atomic_inside = mask(); }
    return mask();
}
uint32_t nova_atomic_break(void) {
    ATOMIC_BLOCK_RESTORESTATE { nova_atomic_inside = mask(); break; }
    return mask();
}
uint32_t nova_atomic_return(void) {
    ATOMIC_BLOCK_RESTORESTATE { nova_atomic_inside = mask(); return 9; }
    return 0;
}
uint32_t nova_atomic_nested(void) {
    ATOMIC_BLOCK_RESTORESTATE {
        ATOMIC_BLOCK_RESTORESTATE { nova_atomic_inside = mask(); }
        nova_atomic_inside |= mask() << 1;
    }
    return mask();
}
