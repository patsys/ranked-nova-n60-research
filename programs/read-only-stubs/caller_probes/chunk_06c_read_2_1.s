mov r0, r1; ldrb r0, [r0, #2]; lsrs r0, #4; lsls r0, #28; lsrs r0, #28; 
        cmp r0, #0
        beq done
        lsls r0, #18
    again:
        subs r0, #1
        bne again
    done:
        movs r0, #0
        bx lr
    