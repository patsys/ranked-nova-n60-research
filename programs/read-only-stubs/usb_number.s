
    mov r0, lr
    movs r2, #0x10
    lsls r2, #8
    adds r2, #0x21
    cmp r0, r2
    bne done
    ldr r0, [sp, #52]
    movs r2, #0x0c
    lsls r2, #8
    adds r2, #0xc3
    cmp r0, r2
    bne done
    adds r2, #6
    str r2, [sp, #52]
    movs r1, #42
done:
    movs r0, #0
    bx lr
