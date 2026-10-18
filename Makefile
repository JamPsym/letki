.DEFAULT_GOAL := all
.DELETE_ON_ERROR:

-include config/local.mk
CONFIG_DEPS := $(wildcard config/local.mk)

VARIANT ?= v3
VARIANTS := v3 v3_1-pmos v3_1-mosfet v3_1-pulse v3_1-interface interface-demo v3-pwm-demo v3-visual-demo v3-scan-demo v3-uart-chain v3-pingpong-demo v3-strip-text v3-strip-five v3-pwm-show v3-general v2 v3-strip-test v3-pwm-experiment
ifeq ($(filter $(VARIANT),$(VARIANTS)),)
$(error Unknown VARIANT '$(VARIANT)'; choose $(VARIANTS))
endif

# WCH GCC is required by the existing fast interrupt handlers.
CROSS_COMPILE ?= $(CURDIR)/.tools/mrs-1.90/RISC-V_Embedded_GCC/bin/riscv-none-embed-
CC := $(CROSS_COMPILE)gcc
OBJCOPY := $(CROSS_COMPILE)objcopy
SIZE := $(CROSS_COMPILE)size
ifneq ($(filter $(VARIANT),v3 v3_1-pmos v3_1-mosfet v3_1-pulse v3_1-interface interface-demo v3-pwm-demo v3-visual-demo v3-scan-demo v3-uart-chain v3-pingpong-demo v3-strip-text v3-strip-five v3-pwm-show v3-general),)
SOURCE_DIR := firmware/$(VARIANT)
BUILD_DIR := build/$(VARIANT)
ifeq ($(VARIANT),v3-pwm-demo)
SOURCE_DIR := firmware/v3
EXPERIMENT_DIR := firmware/pwm-demo/User
endif
ifeq ($(VARIANT),v3-visual-demo)
SOURCE_DIR := firmware/v3
EXPERIMENT_DIR := firmware/visual-demo/User
CPPFLAGS += -DDISPLAY_LEVELS
endif
ifeq ($(VARIANT),v3-scan-demo)
SOURCE_DIR := firmware/v3
EXPERIMENT_DIR := firmware/scan-demo/User
endif
ifeq ($(VARIANT),v3-uart-chain)
SOURCE_DIR := firmware/v3
EXPERIMENT_DIR := firmware/uart-chain/User
endif
ifeq ($(VARIANT),v3-pingpong-demo)
ROLE ?= left
ifeq ($(filter $(ROLE),left right),)
$(error Ping-pong ROLE must be left or right)
endif
SOURCE_DIR := firmware/v3
EXPERIMENT_DIR := firmware/pingpong-demo/User
I2C_SHARED_DIR := firmware/interface-demo/User
BUILD_DIR := build/v3-pingpong-demo-$(ROLE)
PONG_TILE_left := 0
PONG_TILE_right := 1
CPPFLAGS += -DPONG_TILE=$(PONG_TILE_$(ROLE))
endif
ifeq ($(VARIANT),v3-strip-text)
ROLE ?= left
ifeq ($(filter $(ROLE),left right),)
$(error Strip text ROLE must be left or right)
endif
SOURCE_DIR := firmware/v3
EXPERIMENT_DIR := firmware/strip-text/User
BUILD_DIR := build/v3-strip-text-$(ROLE)
STRIP_TILE_left := 0
STRIP_TILE_right := 1
CPPFLAGS += -DSTRIP_TILE=$(STRIP_TILE_$(ROLE))
OPT ?= -Os
endif
ifeq ($(VARIANT),v3-strip-five)
ROLE ?= head
ifeq ($(filter $(ROLE),head tile1 tile2 tile3 tile4),)
$(error Five-tile ROLE must be head, tile1, tile2, tile3 or tile4)
endif
SOURCE_DIR := firmware/v3
EXPERIMENT_DIR := firmware/strip-text/User
BUILD_DIR := build/v3-strip-five-$(ROLE)
STRIP_TILE_head := 0
STRIP_TILE_tile1 := 1
STRIP_TILE_tile2 := 2
STRIP_TILE_tile3 := 3
STRIP_TILE_tile4 := 4
CPPFLAGS += -DSTRIP_TILE=$(STRIP_TILE_$(ROLE)) -DSTRIP_TILES=5 -DSCENE_COLUMNS=40U
OPT ?= -Os
endif
ifeq ($(VARIANT),v3-pwm-show)
ROLE ?= head
ifeq ($(filter $(ROLE),head tile1 tile2 tile3 tile4),)
$(error Five-tile ROLE must be head, tile1, tile2, tile3 or tile4)
endif
SOURCE_DIR := firmware/v3
EXPERIMENT_DIR := firmware/pwm-show/User
BUILD_DIR := build/v3-pwm-show-$(ROLE)
STRIP_TILE_head := 0
STRIP_TILE_tile1 := 1
STRIP_TILE_tile2 := 2
STRIP_TILE_tile3 := 3
STRIP_TILE_tile4 := 4
CPPFLAGS += -DSTRIP_TILE=$(STRIP_TILE_$(ROLE)) -DDISPLAY_LEVELS -Ihost/pwm-show -Ifirmware/strip-text/User
OPT ?= -Os
endif
ifeq ($(VARIANT),v3-general)
ROLE ?= head
ifeq ($(filter $(ROLE),head tile1 tile2 tile3 tile4),)
$(error General ROLE must be head, tile1, tile2, tile3 or tile4)
endif
SOURCE_DIR := firmware/v3
EXPERIMENT_DIR := firmware/general/User
BUILD_DIR := build/v3-general-$(ROLE)
GENERAL_TILE_head := 0
GENERAL_TILE_tile1 := 1
GENERAL_TILE_tile2 := 2
GENERAL_TILE_tile3 := 3
GENERAL_TILE_tile4 := 4
CPPFLAGS += -DGENERAL_TILE=$(GENERAL_TILE_$(ROLE)) -DDISPLAY_LEVELS -DDISPLAY_GENERAL
OPT ?= -Os
endif
ifeq ($(VARIANT),v3_1-pmos)
SOURCE_DIR := firmware/v3
EXPERIMENT_DIR := firmware/v3_1-pmos/User
endif
ifeq ($(VARIANT),v3_1-mosfet)
SOURCE_DIR := firmware/v3
EXPERIMENT_DIR := firmware/v3_1-mosfet/User
endif
ifeq ($(VARIANT),v3_1-pulse)
SOURCE_DIR := firmware/v3
EXPERIMENT_DIR := firmware/v3_1-pulse/User
endif
ifeq ($(VARIANT),v3_1-interface)
SOURCE_DIR := firmware/interface-demo
EXPERIMENT_DIR := firmware/v3_1-interface/User
endif
ifneq ($(filter $(VARIANT),interface-demo v3_1-interface),)
ROLE ?= uart
ifeq ($(filter $(ROLE),uart controller target),)
$(error Unknown ROLE '$(ROLE)'; choose uart, controller or target)
endif
ifneq ($(ROLE),uart)
BUILD_DIR := build/$(VARIANT)-$(ROLE)
endif
BOOT_ROLE_uart := BUS_OFF
BOOT_ROLE_controller := BUS_CONTROLLER
BOOT_ROLE_target := BUS_TARGET
CPPFLAGS += -DINTERFACE_BOOT_MODE=$(BOOT_ROLE_$(ROLE))
endif
else
SOURCE_DIR := archive/firmware/$(VARIANT)
BUILD_DIR := build/archive/$(VARIANT)
endif
TARGET := $(BUILD_DIR)/letki
C_SOURCES := $(sort $(wildcard $(SOURCE_DIR)/User/*.c $(SOURCE_DIR)/Core/*.c $(SOURCE_DIR)/Debug/*.c $(SOURCE_DIR)/Peripheral/src/*.c))
ASM_SOURCES := $(wildcard $(SOURCE_DIR)/Startup/*.S)
OBJECTS := $(patsubst $(SOURCE_DIR)/%.c,$(BUILD_DIR)/%.o,$(C_SOURCES)) $(patsubst $(SOURCE_DIR)/%.S,$(BUILD_DIR)/%.o,$(ASM_SOURCES))
ifneq ($(EXPERIMENT_DIR),)
EXPERIMENT_SHARED := system_ch32v00x.c ch32v00x_it.c uart.c uart_line.c swio.c
ifneq ($(filter $(VARIANT),v3_1-pmos v3_1-mosfet),)
EXPERIMENT_SHARED := $(notdir $(filter-out $(SOURCE_DIR)/User/display.c,$(wildcard $(SOURCE_DIR)/User/*.c)))
endif
ifeq ($(VARIANT),v3_1-pulse)
EXPERIMENT_SHARED := $(notdir $(filter-out $(SOURCE_DIR)/User/display.c $(SOURCE_DIR)/User/main.c,$(wildcard $(SOURCE_DIR)/User/*.c)))
endif
ifeq ($(VARIANT),v3_1-interface)
EXPERIMENT_SHARED := system_ch32v00x.c ch32v00x_it.c uart.c swio.c bus.c protocol.c
endif
ifeq ($(VARIANT),v3-visual-demo)
EXPERIMENT_SHARED += display.c brightness.c speed.c
endif
ifeq ($(VARIANT),v3-scan-demo)
EXPERIMENT_SHARED += display.c
endif
ifeq ($(VARIANT),v3-uart-chain)
EXPERIMENT_SHARED += display.c
endif
ifeq ($(VARIANT),v3-pingpong-demo)
EXPERIMENT_SHARED := system_ch32v00x.c ch32v00x_it.c display.c swio.c
endif
ifneq ($(filter $(VARIANT),v3-strip-text v3-strip-five),)
EXPERIMENT_SHARED := system_ch32v00x.c ch32v00x_it.c display.c swio.c uart.c
ifeq ($(STRIP_TILE_$(ROLE)),0)
EXPERIMENT_SHARED += message.c speed.c brightness.c frame_input.c font_compact.c uart_line.c
endif
endif
ifeq ($(VARIANT),v3-pwm-show)
EXPERIMENT_SHARED := system_ch32v00x.c ch32v00x_it.c display.c swio.c uart.c
ifeq ($(ROLE),head)
EXPERIMENT_SHARED += brightness.c speed.c uart_line.c
endif
endif
ifeq ($(VARIANT),v3-general)
EXPERIMENT_SHARED := system_ch32v00x.c ch32v00x_it.c display.c uart.c
endif
C_SOURCES := $(sort $(wildcard $(SOURCE_DIR)/Core/*.c $(SOURCE_DIR)/Debug/*.c $(SOURCE_DIR)/Peripheral/src/*.c) \
             $(addprefix $(SOURCE_DIR)/User/,$(EXPERIMENT_SHARED)) \
             $(wildcard $(EXPERIMENT_DIR)/*.c))
OBJECTS := $(patsubst $(SOURCE_DIR)/%.c,$(BUILD_DIR)/%.o,$(filter $(SOURCE_DIR)/%,$(C_SOURCES))) \
           $(patsubst $(EXPERIMENT_DIR)/%.c,$(BUILD_DIR)/pwm/%.o,$(filter $(EXPERIMENT_DIR)/%,$(C_SOURCES))) \
           $(patsubst $(SOURCE_DIR)/%.S,$(BUILD_DIR)/%.o,$(ASM_SOURCES))
endif
ifneq ($(I2C_SHARED_DIR),)
C_SOURCES += $(I2C_SHARED_DIR)/bus.c $(I2C_SHARED_DIR)/protocol.c
OBJECTS += $(BUILD_DIR)/i2c/bus.o $(BUILD_DIR)/i2c/protocol.o
endif
ifneq ($(filter $(VARIANT),v3-strip-text v3-strip-five v3-pwm-show),)
C_SOURCES += firmware/interface-demo/User/protocol.c
OBJECTS += $(BUILD_DIR)/strip-protocol.o
$(BUILD_DIR)/strip-protocol.o: firmware/interface-demo/User/protocol.c Makefile $(CONFIG_DEPS)
	@mkdir -p "$(@D)"
	"$(CC)" $(CPPFLAGS) $(CFLAGS) -MMD -MP -c "$<" -o "$@"
endif

ARCH_FLAGS := -march=rv32ecxw -mabi=ilp32e -msmall-data-limit=0 -msave-restore
ifneq ($(filter $(VARIANT),v3_1-pulse v3_1-interface),)
OPT ?= -Os
else
OPT ?= -O0
endif
CPPFLAGS += $(addprefix -I,$(addprefix $(SOURCE_DIR)/,User Core Debug Peripheral/inc))
CPPFLAGS += $(if $(EXPERIMENT_DIR),-I$(EXPERIMENT_DIR))
CPPFLAGS += $(if $(I2C_SHARED_DIR),-I$(I2C_SHARED_DIR))
ifneq ($(filter $(VARIANT),v3-strip-text v3-strip-five v3-pwm-show),)
CPPFLAGS += -Ifirmware/interface-demo/User
endif
CFLAGS += $(ARCH_FLAGS) $(OPT) -g -std=gnu99 -fsigned-char -ffunction-sections -fdata-sections -fno-common -Wunused -Wuninitialized
CFLAGS += $(if $(filter 1,$(STACK_USAGE)),-fstack-usage)
ASFLAGS += $(ARCH_FLAGS) -g
LDFLAGS += $(ARCH_FLAGS) -T$(SOURCE_DIR)/Ld/Link.ld -nostartfiles -Wl,--gc-sections,-Map,$(TARGET).map --specs=nano.specs --specs=nosys.specs
ifeq ($(VARIANT),v3-general)
LDFLAGS := $(subst -Tfirmware/v3/Ld/Link.ld,-Tfirmware/general/Link.ld,$(LDFLAGS))
endif
LDLIBS += -lprintf

.PHONY: all all-variants interface-demos pingpong-demos strip-text-images strip-five-images pwm-show-images renderer-pwm renderer renderer-run renderer-text renderer-test doctor compdb clean help test tui tui-demo pcb-tools pcb-doctor pcb-check pcb-preview
all: $(TARGET).elf $(TARGET).hex $(TARGET).bin

$(BUILD_DIR)/%.o: $(SOURCE_DIR)/%.c Makefile $(CONFIG_DEPS)
	@mkdir -p "$(@D)"
	"$(CC)" $(CPPFLAGS) $(CFLAGS) -MMD -MP -c "$<" -o "$@"

ifneq ($(EXPERIMENT_DIR),)
$(BUILD_DIR)/pwm/%.o: $(EXPERIMENT_DIR)/%.c Makefile $(CONFIG_DEPS)
	@mkdir -p "$(@D)"
	"$(CC)" $(CPPFLAGS) $(CFLAGS) -MMD -MP -c "$<" -o "$@"
endif
ifneq ($(I2C_SHARED_DIR),)
$(BUILD_DIR)/i2c/%.o: $(I2C_SHARED_DIR)/%.c Makefile $(CONFIG_DEPS)
	@mkdir -p "$(@D)"
	"$(CC)" $(CPPFLAGS) $(CFLAGS) -MMD -MP -c "$<" -o "$@"
endif

$(BUILD_DIR)/%.o: $(SOURCE_DIR)/%.S Makefile $(CONFIG_DEPS)
	@mkdir -p "$(@D)"
	"$(CC)" $(CPPFLAGS) $(ASFLAGS) -MMD -MP -c "$<" -o "$@"

$(TARGET).elf: $(OBJECTS) $(SOURCE_DIR)/Ld/Link.ld $(if $(filter v3-general,$(VARIANT)),firmware/general/Link.ld) Makefile $(CONFIG_DEPS)
	"$(CC)" $(LDFLAGS) $(OBJECTS) $(LDLIBS) -o "$@"
	"$(SIZE)" "$@"

$(TARGET).hex: $(TARGET).elf
	"$(OBJCOPY)" -O ihex "$<" "$@"

$(TARGET).bin: $(TARGET).elf
	"$(OBJCOPY)" -O binary "$<" "$@"

all-variants:
	$(MAKE) general-images
	$(MAKE) pwm-show-images
	$(MAKE) strip-five-images
	$(MAKE) VARIANT=v2 all
	$(MAKE) VARIANT=v3 all
	$(MAKE) VARIANT=interface-demo ROLE=uart all
	$(MAKE) VARIANT=interface-demo ROLE=controller all
	$(MAKE) VARIANT=interface-demo ROLE=target all
	$(MAKE) VARIANT=v3-strip-test all
	$(MAKE) VARIANT=v3-pwm-experiment all
	$(MAKE) VARIANT=v3-pwm-demo all
	$(MAKE) VARIANT=v3-visual-demo all
	$(MAKE) VARIANT=v3-scan-demo all
	$(MAKE) VARIANT=v3-uart-chain all
	$(MAKE) VARIANT=v3-pingpong-demo ROLE=left all
	$(MAKE) VARIANT=v3-pingpong-demo ROLE=right all
	$(MAKE) VARIANT=v3-strip-text ROLE=left all
	$(MAKE) VARIANT=v3-strip-text ROLE=right all

interface-demos:
	$(MAKE) VARIANT=interface-demo ROLE=uart all
	$(MAKE) VARIANT=interface-demo ROLE=controller all
	$(MAKE) VARIANT=interface-demo ROLE=target all

pingpong-demos:
	$(MAKE) VARIANT=v3-pingpong-demo ROLE=left all
	$(MAKE) VARIANT=v3-pingpong-demo ROLE=right all

pwm-show-images:
	$(MAKE) VARIANT=v3-pwm-show ROLE=head all
	$(MAKE) VARIANT=v3-pwm-show ROLE=tile1 all
	$(MAKE) VARIANT=v3-pwm-show ROLE=tile2 all
	$(MAKE) VARIANT=v3-pwm-show ROLE=tile3 all
	$(MAKE) VARIANT=v3-pwm-show ROLE=tile4 all

strip-five-images:
	$(MAKE) VARIANT=v3-strip-five ROLE=head all
	$(MAKE) VARIANT=v3-strip-five ROLE=tile1 all
	$(MAKE) VARIANT=v3-strip-five ROLE=tile2 all
	$(MAKE) VARIANT=v3-strip-five ROLE=tile3 all
	$(MAKE) VARIANT=v3-strip-five ROLE=tile4 all

strip-text-images:
	$(MAKE) VARIANT=v3-strip-text ROLE=left all
	$(MAKE) VARIANT=v3-strip-text ROLE=right all

renderer:
	$(MAKE) -f host/renderer/Makefile all HOST_CC="$(HOST_CC)"

BOARDS ?= 2
renderer-run: renderer
	build/renderer/letki-renderer --boards "$(BOARDS)"

renderer-pwm: renderer
	python3 scripts/demo_pwm_show.py

renderer-text: renderer
	python3 scripts/demo_strip_text.py

renderer-test:
	$(MAKE) -f host/renderer/Makefile check HOST_CC="$(HOST_CC)"

tui:
	python3 scripts/letki_tui.py $(if $(PORT),--port "$(PORT)")

tui-demo:
	python3 scripts/letki_tui.py --demo

doctor:
	@"$(CC)" --version || { echo 'Set CROSS_COMPILE in config/local.mk; see docs/arch-setup.md.'; exit 1; }
	@printf '%s\n' '__attribute__((interrupt("WCH-Interrupt-fast"))) void irq(void) {}' | "$(CC)" $(ARCH_FLAGS) -Werror=attributes -x c -c -o /dev/null -
	@"$(OBJCOPY)" --version > /dev/null
	@"$(SIZE)" --version > /dev/null
	@echo 'WCH compiler and binary tools are ready.'

compdb:
	python3 scripts/compile_commands.py --compiler "$(CC)" --flags "$(CPPFLAGS) $(CFLAGS)" $(C_SOURCES)

HOST_CC ?= cc
HOST_CXX ?= c++
STRIP_HOST_SOURCES := firmware/strip-text/User/scene.c firmware/strip-text/User/frame_packet.c firmware/interface-demo/User/protocol.c firmware/v3/User/font_compact.c firmware/v3/User/message.c firmware/v3/User/speed.c firmware/v3/User/brightness.c firmware/v3/User/frame_input.c
STRIP_HOST_FLAGS := -std=c99 -Wall -Wextra -Werror -Ifirmware/strip-text/User -Ifirmware/v3/User -Ifirmware/interface-demo/User
test:
	$(MAKE) -f host/general/Makefile check
	@mkdir -p build/tests
	$(HOST_CC) $(STRIP_HOST_FLAGS) $(STRIP_HOST_SOURCES) tests/test_strip_scene.c -o build/tests/test_strip_scene
	build/tests/test_strip_scene
	$(HOST_CC) $(STRIP_HOST_FLAGS) -DSTRIP_TILE=0 -Itests/mock_interfaces $(STRIP_HOST_SOURCES) firmware/v3/User/uart_line.c tests/test_strip_app.c -o build/tests/test_strip_left
	build/tests/test_strip_left
	$(HOST_CC) $(STRIP_HOST_FLAGS) -DSTRIP_TILE=0 -DSTRIP_TILES=5 -DSCENE_COLUMNS=40U -Itests/mock_interfaces $(STRIP_HOST_SOURCES) firmware/v3/User/uart_line.c tests/test_strip_five.c -o build/tests/test_strip_five
	build/tests/test_strip_five
	$(HOST_CC) -std=c99 -Wall -Wextra -Werror -DSTRIP_TILE=0 -DDISPLAY_LEVELS -Itests/mock_interfaces -Ihost/pwm-show -Ifirmware/v3/User -Ifirmware/strip-text/User -Ifirmware/interface-demo/User host/pwm-show/pwm_show.c firmware/pwm-show/User/frame_packet.c firmware/interface-demo/User/protocol.c firmware/v3/User/uart_line.c firmware/v3/User/speed.c firmware/v3/User/brightness.c tests/test_pwm_show_app.c -o build/tests/test_pwm_show_app
	build/tests/test_pwm_show_app
	$(HOST_CC) -std=c99 -Wall -Wextra -Werror -DSTRIP_TILE=4 -DDISPLAY_LEVELS -Itests/mock_interfaces -Ihost/pwm-show -Ifirmware/v3/User -Ifirmware/strip-text/User -Ifirmware/interface-demo/User host/pwm-show/pwm_show.c firmware/pwm-show/User/frame_packet.c firmware/interface-demo/User/protocol.c tests/test_pwm_show_app.c -o build/tests/test_pwm_show_receiver
	build/tests/test_pwm_show_receiver
	$(HOST_CC) $(STRIP_HOST_FLAGS) -DSTRIP_TILE=1 -Itests/mock_interfaces $(STRIP_HOST_SOURCES) tests/test_strip_app.c -o build/tests/test_strip_right
	build/tests/test_strip_right
	$(HOST_CC) $(STRIP_HOST_FLAGS) -Itests/mock_interfaces firmware/strip-text/User/frame_bus.c firmware/strip-text/User/frame_packet.c firmware/interface-demo/User/protocol.c tests/test_strip_bus.c -o build/tests/test_strip_bus
	build/tests/test_strip_bus
	$(HOST_CC) $(STRIP_HOST_FLAGS) -DSTRIP_TILE=4 -Itests/mock_interfaces firmware/strip-text/User/frame_bus.c firmware/strip-text/User/frame_packet.c firmware/interface-demo/User/protocol.c tests/test_strip_bus.c -o build/tests/test_strip_bus_last
	build/tests/test_strip_bus_last
	$(HOST_CC) -std=c99 -Wall -Wextra -Werror -Ifirmware/pingpong-demo/User firmware/pingpong-demo/User/pong.c tests/test_pong.c -o build/tests/test_pong
	build/tests/test_pong
	$(HOST_CC) -std=c99 -Wall -Wextra -Werror -DPONG_TILE=0 -Itests/mock_interfaces -Ifirmware/v3/User -Ifirmware/pingpong-demo/User -Ifirmware/interface-demo/User firmware/pingpong-demo/User/pong.c tests/test_pong_app.c -o build/tests/test_pong_left
	build/tests/test_pong_left
	$(HOST_CC) -std=c99 -Wall -Wextra -Werror -DPONG_TILE=1 -Itests/mock_interfaces -Ifirmware/v3/User -Ifirmware/pingpong-demo/User -Ifirmware/interface-demo/User firmware/pingpong-demo/User/pong.c tests/test_pong_app.c -o build/tests/test_pong_right
	build/tests/test_pong_right
	$(HOST_CC) -std=c99 -Wall -Wextra -Werror -Ifirmware/v3/User firmware/v3/User/font.c firmware/v3/User/text.c tests/test_text.c -o build/tests/test_text
	build/tests/test_text
	$(HOST_CXX) -std=c++11 -Wall -Wextra -Werror -Itests/mock -Ifirmware/v3/User -x c++ firmware/v3/User/display.c tests/test_display.cpp -o build/tests/test_display
	build/tests/test_display
	$(HOST_CXX) -std=c++11 -Wall -Wextra -Werror -DDISPLAY_LEVELS -Itests/mock -Ifirmware/v3/User -Ifirmware/visual-demo/User -x c++ firmware/v3/User/display.c firmware/visual-demo/User/wave.c firmware/v3/User/brightness.c firmware/v3/User/speed.c firmware/v3/User/uart_line.c tests/test_visual.cpp -o build/tests/test_visual
	build/tests/test_visual
	$(HOST_CXX) -std=c++11 -Wall -Wextra -Werror -Itests/mock_pwm -Ifirmware/pwm-demo/User -x c++ firmware/pwm-demo/User/pwm_display.c tests/test_pwm.cpp -o build/tests/test_pwm
	build/tests/test_pwm
	$(HOST_CC) -std=c99 -Wall -Wextra -Werror -Ifirmware/v3/User -include tests/swio_registers.h firmware/v3/User/swio.c tests/test_swio.c -o build/tests/test_swio
	build/tests/test_swio
	$(HOST_CC) -std=c99 -Wall -Wextra -Werror -Ifirmware/v3/User firmware/v3/User/message.c tests/test_message.c -o build/tests/test_message
	build/tests/test_message
	$(HOST_CC) -std=c99 -Wall -Wextra -Werror -Ifirmware/v3/User firmware/v3/User/speed.c tests/test_speed.c -o build/tests/test_speed
	build/tests/test_speed
	$(HOST_CC) -std=c99 -Wall -Wextra -Werror -Ifirmware/v3/User firmware/v3/User/brightness.c tests/test_brightness.c -o build/tests/test_brightness
	build/tests/test_brightness
	$(HOST_CC) -std=c99 -Wall -Wextra -Werror -Ifirmware/v3/User firmware/v3/User/frame_input.c firmware/v3/User/font_compact.c tests/test_frame_input.c -o build/tests/test_frame_input
	build/tests/test_frame_input
	$(HOST_CC) -std=c99 -Wall -Wextra -Werror -DUART_INTERRUPT= -Itests/mock_interfaces -Ifirmware/v3/User firmware/v3/User/uart.c firmware/v3/User/uart_line.c tests/test_uart_text.c -o build/tests/test_uart_text
	build/tests/test_uart_text
	python3 -m unittest discover -s tests -p 'test_demo_timing.py'
	$(HOST_CC) -std=c99 -Wall -Wextra -Werror -Ifirmware/interface-demo/User firmware/interface-demo/User/protocol.c tests/test_interfaces.c -o build/tests/test_interfaces
	build/tests/test_interfaces
	$(HOST_CC) -std=c99 -Wall -Wextra -Werror -Itests/mock_interfaces -Ifirmware/interface-demo/User firmware/interface-demo/User/bus.c firmware/interface-demo/User/uart.c firmware/interface-demo/User/protocol.c tests/test_interface_drivers.c -o build/tests/test_interface_drivers
	build/tests/test_interface_drivers
	$(HOST_CC) -std=c99 -Wall -Wextra -Werror -DINTERFACE_INTERRUPT= -DINTERFACE_BOOT_MODE=BUS_CONTROLLER -Itests/mock_interfaces -Ifirmware/interface-demo/User firmware/interface-demo/User/protocol.c tests/test_interface_app.c -o build/tests/test_interface_app
	build/tests/test_interface_app
	$(HOST_CC) -std=c99 -Wall -Wextra -Werror -Ifirmware/uart-chain/User firmware/uart-chain/User/chain.c tests/test_uart_chain.c -o build/tests/test_uart_chain
	build/tests/test_uart_chain
	$(HOST_CC) -std=c99 -Wall -Wextra -Werror -Ifirmware/uart-chain/User firmware/uart-chain/User/chain.c tests/uart_chain_relay.c -o build/tests/uart_chain_relay
	python3 -m unittest discover -s tests -p 'test_uart_chain.py'
	python3 -m unittest discover -s tests -p 'test_uart_demo.py'
	python3 -m unittest discover -s tests -p 'test_swio_terminal.py'
	python3 -m unittest discover -s tests -p 'test_letki_tui.py'
	python3 -m unittest discover -s tests -p 'test_uart_link.py'

clean:
	rm -rf -- "$(BUILD_DIR)"

PCB ?= hw/ledkiv4/ledkiv4.kicad_pcb
pcb-tools:
	python3 scripts/setup_kicad_routing.py

pcb-doctor:
	python3 scripts/kicad_routing.py doctor

pcb-check:
	python3 scripts/kicad_routing.py check --board "$(PCB)"

pcb-preview:
	python3 scripts/kicad_routing.py render --board "$(PCB)"

help:
	@echo 'make general-images               Build the general firmware candidate (never flash)'
	@echo 'make general-test                 General protocol/storage/renderer/serial tests'
	@echo 'make general-preview              Export the general text/animation preview'
	@echo 'make renderer-pwm                  Open the five-tile PWM simulation'
	@echo 'make pwm-show-images               Build the unflashed five-board PWM candidate'
	@echo 'make strip-five-images             Build head + four addressed text receivers'
	@echo 'make strip-text-images             Build left/right standard text + UART images'
	@echo 'make renderer-text                 Demonstrate their default in the native window'
	@echo 'make renderer-run BOARDS=5         Native Wayland test strip with agent controls'
	@echo 'make renderer-test                 Deterministic native renderer integration checks'
	@echo 'make pingpong-demos               Build two-board I2C ball animation (left/right)'
	@echo 'make pcb-tools / pcb-doctor        Install / check pinned KiCadRoutingTools'
	@echo 'make pcb-check / pcb-preview       Check / render an isolated v4 PCB copy'
	@echo 'make VARIANT=v3-visual-demo       Build standalone gamma radial-wave demo'
	@echo 'make                              Build active v3 text firmware in build/v3'
	@echo 'make VARIANT=interface-demo       Build isolated UART/I2C demo firmware'
	@echo 'make VARIANT=v3-pwm-demo          Build sparse hardware-PWM experiment'
	@echo 'make interface-demos              Build UART, I2C controller and target images'
	@echo 'make tui / tui-demo               Open Vim-style controls / offline preview'
	@echo 'make tui PORT=/dev/ttyACM2         Use the same TUI over USART at 115200 8N1'
	@echo 'make VARIANT=<name>               Build v3, interface-demo or an archived variant'
	@echo 'make all-variants                 Build active and archived firmware'
	@echo 'make doctor                       Check WCH compiler support'
	@echo 'make test                         Host checks for text and display scanning'
	@echo 'make compdb [VARIANT=...]          Select the firmware indexed by clangd'
	@echo 'make clean [VARIANT=...]           Remove native outputs for one variant'

-include $(OBJECTS:.o=.d)

# v3.1 has reversed LED polarity and requires its own bounded-pulse firmware.
.PHONY: v3_1-interface-demos v3_1-test
all-variants: v3_1-builds
.PHONY: v3_1-builds
v3_1-builds: v3_1-interface-demos
	$(MAKE) VARIANT=v3_1-pmos all
	$(MAKE) VARIANT=v3_1-mosfet all
	$(MAKE) VARIANT=v3_1-pulse all

v3_1-interface-demos:
	$(MAKE) VARIANT=v3_1-interface ROLE=uart all
	$(MAKE) VARIANT=v3_1-interface ROLE=controller all
	$(MAKE) VARIANT=v3_1-interface ROLE=target all

test: v3_1-test
v3_1-test:
	@mkdir -p build/tests
	$(HOST_CXX) -std=c++11 -Wall -Wextra -Werror -Itests/mock_pulse -Ifirmware/v3_1-pulse/User -x c++ firmware/v3_1-pulse/User/display.c tests/test_pulse_display.cpp -o build/tests/test_pulse_display
	build/tests/test_pulse_display
	$(HOST_CXX) -std=c++11 -Wall -Wextra -Werror -Itests/mock -Ifirmware/interface-demo/User -x c++ firmware/v3_1-interface/User/display.c tests/test_v3_1_interface_blank.cpp -o build/tests/test_v3_1_interface_blank
	build/tests/test_v3_1_interface_blank
	$(HOST_CC) -std=c99 -Wall -Wextra -Werror -DV3_1_INTERFACE_TEST -DINTERFACE_INTERRUPT= -DINTERFACE_BOOT_MODE=BUS_CONTROLLER -Itests/mock_v3_1_interfaces -Ifirmware/interface-demo/User firmware/interface-demo/User/protocol.c tests/test_v3_1_interface_app.c -o build/tests/test_v3_1_interface_app
	build/tests/test_v3_1_interface_app
	python3 -m unittest discover -s tests -p 'test_v3_1_qualify.py'

.PHONY: general-images general-test general-preview general-host
general-images:
	$(MAKE) VARIANT=v3-general ROLE=head all
	$(MAKE) VARIANT=v3-general ROLE=tile1 all
	$(MAKE) VARIANT=v3-general ROLE=tile2 all
	$(MAKE) VARIANT=v3-general ROLE=tile3 all
	$(MAKE) VARIANT=v3-general ROLE=tile4 all
general-test:
	$(MAKE) -f host/general/Makefile check
general-host:
	$(MAKE) -f host/general/Makefile all
general-preview: general-host
	python3 scripts/letki_general.py preview config/general/demo.json

.PHONY: player player-run player-test player-sanitize
player: general-host
	$(MAKE) -f host/player/Makefile all
player-run: player
	build/player/letki-player
player-test: general-host
	$(MAKE) -f host/player/Makefile check
player-sanitize: general-host
	$(MAKE) -f host/player/Makefile sanitize

.PHONY: demos-check demos-prepare demo-my-cyganie demo-tubular-bells demo-adagio
demos-check: player
	python3 scripts/prepare_demo_previews.py --no-video
demos-prepare: player
	python3 scripts/prepare_demo_previews.py
demo-my-cyganie: player
	build/player/letki-player --show config/player/my-cyganie-full.json $(if $(PORT),--port "$(PORT)")
demo-tubular-bells: player
	build/player/letki-player --show config/player/tubular-bells-full.json $(if $(PORT),--port "$(PORT)")
demo-adagio: player
	build/player/letki-player --show config/player/adagio-full.json $(if $(PORT),--port "$(PORT)")

.PHONY: control control-run control-test control-desktop control-service-install control-service-run control-gui-test
control: general-host
	$(MAKE) -f host/control/Makefile all
control-run: control
	build/control/letki-control $(if $(PORT),--port "$(PORT)")
control-test: general-host
	$(MAKE) -f host/control/Makefile check
control-desktop: control
	$(MAKE) -f host/control/Makefile desktop
control-service-install: control
	$(MAKE) -f host/control/Makefile service-install
control-service-run: control
	build/control/letkid $(if $(PORT),--port "$(PORT)")
control-gui-test: control
	python3 tests/test_studio.py

.PHONY: demo-lamour-toujours
demo-lamour-toujours: player
	build/player/letki-player --show config/player/lamour-toujours-full.json $(if $(PORT),--port "$(PORT)")

.PHONY: demo-laskowski-2pac
demo-laskowski-2pac: player
	build/player/letki-player --show config/player/laskowski-2pac-full.json $(if $(PORT),--port "$(PORT)")
