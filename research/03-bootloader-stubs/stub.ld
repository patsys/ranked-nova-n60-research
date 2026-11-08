/* Research load address from REPORT.md; available SRAM size is unverified. */
ENTRY(stub_entry)
SECTIONS
{
    . = 0x20000000;
    .text : { KEEP(*(.text.entry)) *(.text*) *(.rodata*) }
    /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.note*) }
    .data : { *(.data*) }
    .bss : { *(.bss*) *(COMMON) }
    ASSERT(SIZEOF(.data) == 0, "Payload must not require initialized globals")
    ASSERT(SIZEOF(.bss) == 0, "Payload must not require zeroed globals")
    ASSERT(SIZEOF(.text) <= 440, "Payload exceeds observed vendor stub size")
}
