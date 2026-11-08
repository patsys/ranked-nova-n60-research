movs r0, #12; lsls r0, #8; adds r0, #211; ldrb r0, [r0]; 
        cmp r0, #0
        beq done
        lsls r0, #15
    loop:
        subs r0, #1
        bne loop
    done:
        movs r0, #0
        bx lr
    