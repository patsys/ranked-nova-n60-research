mov r0, sp; ldr r0, [r0, #52]; mov r1, r0; lsrs r1, #16; eors r0, r1; mov r1, r0; lsrs r1, #8; eors r0, r1; mov r1, r0; lsrs r1, #4; eors r0, r1; movs r1, #15; ands r0, r1
        cmp r0, #0
        beq done
        lsls r0, #18
    loop:
        subs r0, #1
        bne loop
    done:
        movs r0, #0
        bx lr
    