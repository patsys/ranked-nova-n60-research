movs r0, #8
        cmp r0, #0
        beq done
        lsls r0, #18
    loop:
        subs r0, #1
        bne loop
    done:
        movs r0, #0
        bx lr
    