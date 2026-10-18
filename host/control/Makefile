CXX ?= c++
CC ?= cc
OUT := build/control
CORE_PKGS := glib-2.0 json-c
GUI_PKGS := gtk4 libadwaita-1 json-c
CPPFLAGS := -Ihost/control -Ihost/player -Ifirmware/v3/User
CXXFLAGS := -std=c++17 -O2 -g -Wall -Wextra -Werror -pthread
CORE_FLAGS := $(shell pkg-config --cflags $(CORE_PKGS))
CORE_LIBS := $(shell pkg-config --libs $(CORE_PKGS)) -pthread -ldl
GUI_FLAGS := $(shell pkg-config --cflags $(GUI_PKGS))
GUI_LIBS := $(shell pkg-config --libs $(GUI_PKGS)) -pthread
CORE := host/control/text_program.cpp host/control/controller.cpp host/player/link.cpp
FONTS := $(OUT)/font.o $(OUT)/font-large.o
HEADERS := host/control/text_program.hpp host/control/controller.hpp host/control/ipc.hpp host/player/player.hpp
.PHONY: all check sanitize desktop service-install
all: $(OUT)/letki-control $(OUT)/letkid $(OUT)/letkictl
$(OUT):
	mkdir -p $@
$(OUT)/font.o: firmware/v3/User/font_compact.c firmware/v3/User/font.h | $(OUT)
	$(CC) -std=c99 -O2 -Ifirmware/v3/User -c $< -o $@
$(OUT)/font-large.o: firmware/v3/User/font.c firmware/v3/User/font.h | $(OUT)
	$(CC) -std=c99 -O2 -Ifirmware/v3/User -c $< -o $@
$(OUT)/pwm-show.o: host/pwm-show/pwm_show.c host/pwm-show/pwm_show.h | $(OUT)
	$(CC) -std=c99 -O2 -Ihost/pwm-show -c $< -o $@
$(OUT)/letki-control: host/control/studio.cpp host/control/demos.cpp host/control/demos.hpp host/control/ipc.cpp host/control/ipc.hpp $(OUT)/pwm-show.o host/control/Makefile | $(OUT)
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) -Ihost/pwm-show $(GUI_FLAGS) host/control/studio.cpp host/control/demos.cpp host/control/ipc.cpp $(OUT)/pwm-show.o -o $@.new $(GUI_LIBS)
	mv $@.new $@
$(OUT)/letkid: $(CORE) host/control/service.cpp host/control/music_demo.cpp host/control/music_demo.hpp host/control/ipc.cpp $(HEADERS) $(FONTS) host/control/Makefile
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) $(CORE_FLAGS) $(CORE) host/control/service.cpp host/control/music_demo.cpp host/control/ipc.cpp $(FONTS) -o $@.new $(CORE_LIBS)
	mv $@.new $@
$(OUT)/letkictl: host/control/ctl.cpp host/control/ipc.cpp host/control/ipc.hpp host/control/Makefile | $(OUT)
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) $(CORE_FLAGS) host/control/ctl.cpp host/control/ipc.cpp -o $@.new $(CORE_LIBS)
	mv $@.new $@
$(OUT)/test-control: $(CORE) tests/test_control.cpp $(HEADERS) $(FONTS) host/control/Makefile
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) $(CORE_FLAGS) $(CORE) tests/test_control.cpp $(FONTS) -o $@ $(CORE_LIBS)
$(OUT)/test-demos: host/control/demos.cpp host/control/demos.hpp tests/test_control_demos.cpp $(OUT)/pwm-show.o
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) -Ihost/pwm-show host/control/demos.cpp tests/test_control_demos.cpp $(OUT)/pwm-show.o -o $@
check: all $(OUT)/test-control $(OUT)/test-demos
	$(OUT)/test-control
	$(OUT)/test-demos
	python3 tests/test_display_service.py
sanitize: $(FONTS)
	$(CXX) $(CXXFLAGS) -O1 -fsanitize=address,undefined -fno-omit-frame-pointer $(CPPFLAGS) $(CORE_FLAGS) $(CORE) tests/test_control.cpp $(FONTS) -o $(OUT)/test-control-asan $(CORE_LIBS)
	ASAN_OPTIONS=detect_leaks=0 $(OUT)/test-control-asan
$(OUT)/letki-control.desktop: host/control/letki-control.desktop.in host/control/Makefile | $(OUT)
	sed 's|@EXEC@|$(abspath $(OUT)/letki-control)|g' $< > $@
desktop: all $(OUT)/letki-control.desktop
	install -Dm644 $(OUT)/letki-control.desktop "$${XDG_DATA_HOME:-$$HOME/.local/share}/applications/io.github.letki.Studio.desktop"
$(OUT)/letkid.service: host/control/letkid.service.in host/control/Makefile | $(OUT)
	sed -e 's|@EXEC@|$(abspath $(OUT)/letkid)|g' -e 's|@ROOT@|$(CURDIR)|g' $< > $@
service-install: all $(OUT)/letkid.service
	install -Dm644 $(OUT)/letkid.service "$${XDG_CONFIG_HOME:-$$HOME/.config}/systemd/user/letkid.service"
	systemctl --user daemon-reload
