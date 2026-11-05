# Reuse actual ChibiOS generic startup, without selecting an unrelated MCU.
# Including build sets NOVA_PLATFORM_DIR and CHIBIOS.
NOVA_PLATFORM_DIR ?= $(TOP_DIR)/../qmk_port/platform
STARTUPSRC = $(CHIBIOS)/os/common/startup/ARMCMx/compilers/GCC/crt1.c
STARTUPASM = $(CHIBIOS)/os/common/startup/ARMCMx/compilers/GCC/crt0_v6m.S \
             $(CHIBIOS)/os/common/startup/ARMCMx/compilers/GCC/vectors.S
STARTUPINC = $(NOVA_PLATFORM_DIR) \
             $(CHIBIOS)/os/common/portability/GCC \
             $(CHIBIOS)/os/common/startup/ARMCMx/compilers/GCC
STARTUPLD = $(CHIBIOS)/os/common/startup/ARMCMx/compilers/GCC/ld
ALLXASMSRC += $(STARTUPASM)
ALLCSRC += $(STARTUPSRC)
ALLINC += $(STARTUPINC)
# Preserved native bootloader forwards exceptions to vectors fixed at0x2000.
# Do not write an unconfirmed VTOR or remap/copy vectors into RAM.
OPT_DEFS += -DCRT0_VTOR_INIT=FALSE -DCRT0_INIT_VECTORS=FALSE
MCU_LDSCRIPT ?= NOVA_RESEARCH
LDFLAGS += -L$(NOVA_PLATFORM_DIR)
