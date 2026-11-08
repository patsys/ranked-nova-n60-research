
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
        movs r2, #0x20
        lsls r2, #24
        adds r2, #255
        adds r2, #66
        str r2, [sp, #52]
done:
        movs r0, #0
        bx lr
    
/* tail at 0x20000140 */
movs r0, #0; lsls r0, #8; adds r0, #0; lsls r0, #8; adds r0, #128; lsls r0, #8; adds r0, #0
        mov r2, r4
        adds r2, #8
        movs r1, #56
copy_loop:
        ldrb r3, [r0]
        strb r3, [r2]
        adds r0, #1
        adds r2, #1
        subs r1, #1
        bne copy_loop
        movs r1, #56
        strh r1, [r4, #4]
        mov r0, r4
        adds r0, #255
        adds r0, #255
        adds r0, #2
        ldr r0, [r0, #20]
        blx r0
        movs r3, #0x0e
        lsls r3, #8
        adds r3, #0x71
        bx r3
    