movs r0, #15; lsls r0, #8; adds r0, #98; ldrb r0, [r0]; lsrs r0, #4; movs r1, #15; ands r0, r1
        cmp r0, #0
        beq done
        lsls r0, #18
    loop:
        subs r0, #1
        bne loop
    done:
        movs r0, #0
        bx lr
    