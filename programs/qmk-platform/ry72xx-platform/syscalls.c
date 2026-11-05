// Copyright 2026 patsys
// SPDX-License-Identifier: GPL-3.0-or-later

#include <errno.h>
#include <stddef.h>
#include <sys/types.h>

// No filesystem or console transport is provided by this platform. Report
// failure explicitly if libc attempts to access one; never discard output
// while reporting a successful write.
int _close(int fd) {
    (void)fd;
    errno = EBADF;
    return -1;
}

off_t _lseek(int fd, off_t offset, int whence) {
    (void)fd;
    (void)offset;
    (void)whence;
    errno = ESPIPE;
    return (off_t)-1;
}

int _read(int fd, void *buffer, size_t count) {
    (void)fd;
    (void)buffer;
    (void)count;
    errno = ENOSYS;
    return -1;
}

int _write(int fd, const void *buffer, size_t count) {
    (void)fd;
    (void)buffer;
    (void)count;
    errno = ENOSYS;
    return -1;
}
