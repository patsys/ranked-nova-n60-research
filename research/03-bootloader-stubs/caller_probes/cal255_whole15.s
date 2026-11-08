movs r0, #255
        cmp r0, #0
        beq done
        lsls r0, #15
    loop:
        subs r0, #1
        bne loop
    done:
        movs r0, #0
        bx lr
    