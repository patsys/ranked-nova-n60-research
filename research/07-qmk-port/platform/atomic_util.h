#pragma once
#include <stdint.h>
static inline uint32_t nova_irq_save_disable(void) {
    uint32_t previous;
    __asm__ volatile("mrs %0, primask\ncpsid i" : "=r"(previous) :: "memory");
    return previous;
}
static inline void nova_irq_restore(uint32_t *previous) {
    __asm__ volatile("msr primask, %0" :: "r"(*previous) : "memory");
}
#define ATOMIC_RESTORESTATE 0
#define ATOMIC_FORCEON 1
#define ATOMIC_BLOCK(type) \
    for (uint32_t nova_irq_state __attribute__((cleanup(nova_irq_restore))) = \
             ((type) ? (nova_irq_save_disable(), 0U) : nova_irq_save_disable()), \
                  nova_irq_once = 1; nova_irq_once; nova_irq_once = 0)
#define ATOMIC_BLOCK_RESTORESTATE ATOMIC_BLOCK(ATOMIC_RESTORESTATE)
#define ATOMIC_BLOCK_FORCEON ATOMIC_BLOCK(ATOMIC_FORCEON)
