HOST_CC ?= cc
HOST_CXX ?= c++
OUT := build/general
CORE := firmware/general/User/counter.c firmware/general/User/router.c firmware/general/User/wire.c firmware/general/User/node.c firmware/general/User/render.c
FLAGS := -std=c99 -O2 -g -Wall -Wextra -Werror -Ifirmware/general/User
.PHONY: all check
all: $(OUT)/libletki-general.so
$(OUT)/libletki-general.so: $(CORE) host/pwm-show/pwm_show.c host/pwm-show/pwm_show.h firmware/general/User/general.h host/general/sim.c firmware/v3/User/font_compact.c host/general/Makefile
	@mkdir -p $(OUT)
	$(HOST_CC) $(FLAGS) -fPIC -shared $(CORE) host/pwm-show/pwm_show.c -Ihost/pwm-show host/general/sim.c firmware/v3/User/font_compact.c -Ifirmware/v3/User -o $@
check: all $(OUT)/test-clock $(OUT)/test-display $(OUT)/test-flash
	$(OUT)/test-clock
	$(OUT)/test-display
	$(OUT)/test-flash
	python3 -m unittest discover -s tests -p 'test_general*.py'

$(OUT)/clock-wire.o: firmware/general/User/wire.c firmware/general/User/general.h
	@mkdir -p $(OUT)
	$(HOST_CC) $(FLAGS) -c $< -o $@
$(OUT)/clock-counter.o: firmware/general/User/counter.c firmware/general/User/general.h
	@mkdir -p $(OUT)
	$(HOST_CC) $(FLAGS) -c $< -o $@
$(OUT)/test-clock: tests/test_general_clock.cpp tests/mock_general_clock/ch32v00x.h firmware/general/User/clock.c firmware/general/User/clock.h $(OUT)/clock-wire.o $(OUT)/clock-counter.o
	$(HOST_CXX) -std=c++11 -Wall -Wextra -Werror -Wno-missing-field-initializers -Itests/mock_general_clock -Ifirmware/general/User $< $(OUT)/clock-wire.o $(OUT)/clock-counter.o -o $@

$(OUT)/test-display: tests/test_general_display.cpp firmware/v3/User/display.c firmware/v3/User/display.h $(wildcard tests/mock_pwm/*)
	@mkdir -p $(OUT)
	$(HOST_CXX) -std=c++11 -Wall -Wextra -Werror -DDISPLAY_LEVELS -DDISPLAY_GENERAL -Itests/mock -Ifirmware/v3/User -x c++ firmware/v3/User/display.c $< -o $@

$(OUT)/test-flash: tests/test_general_flash.cpp firmware/general/User/content_flash.h $(OUT)/clock-wire.o
	$(HOST_CXX) -std=c++11 -Wall -Wextra -Werror -Ifirmware/general/User $< $(OUT)/clock-wire.o -o $@

.PHONY: sanitize
sanitize: $(OUT)/sanitize-core
	ASAN_OPTIONS=detect_leaks=0 $(OUT)/sanitize-core
$(OUT)/sanitize-core: $(CORE) tests/test_general_core.c firmware/general/User/general.h
	@mkdir -p $(OUT)
	$(HOST_CC) -std=c99 -O1 -g -Wall -Wextra -Werror -fsanitize=address,undefined -fno-omit-frame-pointer -Ifirmware/general/User $(CORE) tests/test_general_core.c -o $@
