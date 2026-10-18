HOST_CC ?= cc
OUT := build/renderer
PKGS := wayland-client cairo
WPROTOCOLS := $(shell pkg-config --variable=pkgdatadir wayland-protocols)
XDG_XML := $(WPROTOCOLS)/stable/xdg-shell/xdg-shell.xml
APP_SOURCES := host/pwm-show/pwm_show.c host/renderer/main.c host/renderer/model.c firmware/pingpong-demo/User/pong.c firmware/interface-demo/User/protocol.c firmware/strip-text/User/scene.c firmware/strip-text/User/frame_packet.c firmware/v3/User/font_compact.c firmware/v3/User/message.c firmware/v3/User/speed.c firmware/v3/User/brightness.c firmware/v3/User/frame_input.c
APP_HEADERS := host/pwm-show/pwm_show.h host/renderer/model.h firmware/pingpong-demo/User/pong.h firmware/interface-demo/User/protocol.h $(wildcard firmware/strip-text/User/*.h firmware/v3/User/*.h)
HOST_FLAGS := -std=c11 -O2 -g -Wall -Wextra -Werror -D_POSIX_C_SOURCE=200809L
HOST_INCLUDES := -Ihost/pwm-show -Ihost/renderer -Ifirmware/pingpong-demo/User -Ifirmware/strip-text/User -Ifirmware/v3/User -Ifirmware/interface-demo/User -I$(OUT)

.PHONY: all check
all: $(OUT)/letki-renderer

$(OUT)/xdg-shell-client-protocol.h: $(XDG_XML)
	@mkdir -p $(OUT)
	wayland-scanner client-header $< $@

$(OUT)/xdg-shell-protocol.c: $(XDG_XML)
	@mkdir -p $(OUT)
	wayland-scanner private-code $< $@

$(OUT)/letki-renderer: $(APP_SOURCES) $(APP_HEADERS) $(OUT)/xdg-shell-client-protocol.h $(OUT)/xdg-shell-protocol.c host/renderer/Makefile
	$(HOST_CC) $(HOST_FLAGS) $(HOST_INCLUDES) $$(pkg-config --cflags $(PKGS)) $(APP_SOURCES) $(OUT)/xdg-shell-protocol.c -o $@ $$(pkg-config --libs $(PKGS)) -lm

check: all
	$(HOST_CC) -std=c99 -O2 -Wall -Wextra -Werror -Ihost/pwm-show host/pwm-show/pwm_show.c tests/test_pwm_show.c -o $(OUT)/test-pwm-show
	$(OUT)/test-pwm-show
	python3 tests/test_native_renderer.py
