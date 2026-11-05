/* Cortex-M0 diagnostic payload. See README.md before target integration. */
#include <stdint.h>
#include <stddef.h>

#ifndef READ_BASE
#define READ_BASE 0u
#endif
#ifndef READ_SIZE
#define READ_SIZE 0u /* Reads disabled until a CPU-visible mapping is verified. */
#endif

#define CAPACITY 64u
#define MAGIC 0x524F5354u
enum { PROBE = 0, READ = 1 };
enum { OK = 0, BAD_REQUEST = 1, DENIED = 2 };

/* Caller supplies an aligned, writable RAM object disjoint from code/stack.
 * No pointer received from the device protocol is trusted by this interface.
 * An ABI adapter must validate that the mailbox is RAM before calling us. */
struct mailbox {
    uint32_t magic;
    uint32_t command;
    uint32_t address;
    uint32_t length;
    uint32_t status;
    uint32_t count;
    uint8_t data[CAPACITY];
};

__attribute__((section(".text.entry"), used))
uint32_t stub_entry(volatile struct mailbox *m)
{
    uint32_t command, address, length, offset, i;
    if (m == NULL) return BAD_REQUEST;
    command = m->command;
    address = m->address;
    length = m->length;
    m->count = 0;
    m->status = BAD_REQUEST;
    for (i = 0; i < CAPACITY; ++i) m->data[i] = 0;
    if (m->magic != MAGIC) return BAD_REQUEST;
    if (command == PROBE) {
        m->data[0] = 'R'; m->data[1] = 'O';
        m->data[2] = 'S'; m->data[3] = 'T';
        m->count = 4;
        m->status = OK;
        return OK;
    }
    if (command != READ) return BAD_REQUEST;
    /* Subtraction-based bounds checks avoid address+length overflow. */
    if (length == 0 || length > CAPACITY || address < READ_BASE) {
        m->status = DENIED;
        return DENIED;
    }
    offset = address - READ_BASE;
    if (offset >= READ_SIZE || length > READ_SIZE - offset) {
        m->status = DENIED;
        return DENIED;
    }
    for (i = 0; i < length; ++i)
        m->data[i] = *(volatile const uint8_t *)(uintptr_t)(address + i);
    m->count = length;
    m->status = OK;
    return OK;
}
