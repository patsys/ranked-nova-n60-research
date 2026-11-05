movs r0, #0; 
        cmp r0, #0
        beq done
        lsls r0, #18
    again:
        subs r0, #1
        bne again
    done:
        movs r0, #0
        bx lr
    