
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
        movs r1, #16
        lsls r1, #8
        adds r1, #30
        ldrb r1, [r1]
        adds r2, #6
        str r2, [sp, #52]
done:
        movs r0, #0
        bx lr
    