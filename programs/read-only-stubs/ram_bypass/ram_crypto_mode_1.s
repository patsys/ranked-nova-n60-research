
        mov r0, lr
        movs r2, #0x10
        lsls r2, #8
        adds r2, #0x21
        cmp r0, r2
        bne init_done
        ldr r0, [sp, #52]
        movs r2, #0x0c
        lsls r2, #8
        adds r2, #0xc3
        cmp r0, r2
        bne init_done
        ldr r0, init_flag
        movs r1, #1
        str r1, [r0]
init_done:
        movs r0, #0
        bx lr
        .align 2
init_flag:
        .word 0x20000214
    
/* program at 0x20000140 */

        push {r1,r2,r3,r4,r5,r6,r7,lr}
        mov r5, r1
        ldrh r6, [r4, #4]
        ldrb r3, [r4, #1]
        cmp r3, #11
        beq metadata
        cmp r3, #0
        beq finished
        cmp r3, #10
        bhi finished
        movs r7, #56
        cmp r3, #10
        bne length_ready
        movs r7, #8
length_ready:
        subs r3, #1
        movs r2, #56
        muls r2, r3, r2
        adds r5, r5, r2
        mov r2, r4
        adds r2, #8
        mov r3, r7
copy:
        ldrb r0, [r5]
        strb r0, [r2]
        adds r5, #1
        adds r2, #1
        subs r3, #1
        bne copy
        b send
metadata:
        movs r7, #12
        ldr r0, [sp]
        str r0, [r4, #8]
        str r4, [r4, #12]
        ldr r0, program_flag
        ldr r0, [r0]
        str r0, [r4, #16]
send:
        mov r1, r7
        strh r1, [r4, #4]
        mov r0, r4
        adds r0, #255
        adds r0, #255
        adds r0, #2
        ldr r0, [r0, #20]
        blx r0
        movs r0, #1
        lsls r0, #18
pause:
        subs r0, #1
        bne pause
        strh r6, [r4, #4]
finished:
        movs r0, #0
        pop {r1,r2,r3,r4,r5,r6,r7,pc}
        .align 2
program_flag:
        .word 0x20000214
    