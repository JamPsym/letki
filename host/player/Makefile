CXX ?= c++
CC ?= cc
OUT := build/player
PKGS := portaudio-2.0 sndfile sdl2 json-c libavformat libavcodec libavutil libswscale
CXXFLAGS := -std=c++17 -O2 -g -Wall -Wextra -Werror -pthread
CPPFLAGS := -Ihost/player -Ihost/pwm-show -Ifirmware/v3/User $(shell pkg-config --cflags $(PKGS))
LDLIBS := $(shell pkg-config --libs $(PKGS)) -pthread -ldl
SOURCES := host/player/show.cpp host/player/audio.cpp host/player/link.cpp host/player/video.cpp host/player/theatre.cpp host/player/dance.cpp host/player/rhythm.cpp host/player/fusion.cpp host/player/lamour.cpp host/player/adagio.cpp host/player/bells.cpp
.PHONY: all check sanitize
all: $(OUT)/letki-player
$(OUT):
	mkdir -p $@
$(OUT)/font.o: firmware/v3/User/font_compact.c firmware/v3/User/font.h | $(OUT)
	$(CC) -std=c99 -O2 -Ifirmware/v3/User -c $< -o $@
$(OUT)/pwm.o: host/pwm-show/pwm_show.c host/pwm-show/pwm_show.h | $(OUT)
	$(CC) -std=c99 -O2 -Ihost/pwm-show -c $< -o $@
$(OUT)/letki-player: $(SOURCES) host/player/main.cpp host/player/player.hpp host/player/dance.hpp host/player/rhythm.hpp host/player/fusion.hpp host/player/lamour.hpp host/player/adagio.hpp host/player/bells.hpp $(OUT)/font.o $(OUT)/pwm.o host/player/Makefile
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) $(SOURCES) host/player/main.cpp $(OUT)/font.o $(OUT)/pwm.o -o $@ $(LDLIBS)
$(OUT)/test-player: $(SOURCES) tests/test_player.cpp host/player/player.hpp host/player/dance.hpp host/player/rhythm.hpp host/player/fusion.hpp host/player/lamour.hpp host/player/adagio.hpp host/player/bells.hpp $(OUT)/font.o $(OUT)/pwm.o host/player/Makefile
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) $(SOURCES) tests/test_player.cpp $(OUT)/font.o $(OUT)/pwm.o -o $@ $(LDLIBS) -lutil
check: all $(OUT)/test-fusion $(OUT)/test-player $(OUT)/test-audio $(OUT)/test-video $(OUT)/test-dance $(OUT)/test-rhythm $(OUT)/test-adagio $(OUT)/test-bells
	$(OUT)/test-fusion
	$(OUT)/test-player
	$(OUT)/test-audio
	$(OUT)/test-video
	$(OUT)/test-dance
	$(OUT)/test-rhythm
	$(OUT)/test-adagio
	$(OUT)/test-bells
	python3 tests/test_player_cli.py
	python3 tests/test_player_words.py
sanitize: $(OUT)/test-video.mkv | $(OUT)
	$(CXX) $(CXXFLAGS) -O1 -fsanitize=address,undefined -fno-omit-frame-pointer $(CPPFLAGS) $(SOURCES) tests/test_player.cpp $(OUT)/font.o $(OUT)/pwm.o -o $(OUT)/test-player-asan $(LDLIBS) -lutil
	ASAN_OPTIONS=detect_leaks=0 $(OUT)/test-player-asan
	$(CXX) $(CXXFLAGS) -O1 -fsanitize=address,undefined -fno-omit-frame-pointer $(CPPFLAGS) host/player/audio.cpp host/player/show.cpp host/player/theatre.cpp host/player/dance.cpp host/player/rhythm.cpp host/player/fusion.cpp host/player/lamour.cpp host/player/adagio.cpp host/player/bells.cpp tests/test_player_audio.cpp $(OUT)/font.o $(OUT)/pwm.o -o $(OUT)/test-audio-asan $(LDLIBS)
	ASAN_OPTIONS=detect_leaks=0 $(OUT)/test-audio-asan
	$(CXX) $(CXXFLAGS) -O1 -fsanitize=address,undefined -fno-omit-frame-pointer $(CPPFLAGS) host/player/video.cpp tests/test_player_video.cpp -o $(OUT)/test-video-asan $(LDLIBS)
	ASAN_OPTIONS=detect_leaks=0 $(OUT)/test-video-asan

$(OUT)/test-audio: host/player/audio.cpp host/player/show.cpp host/player/theatre.cpp host/player/dance.cpp host/player/rhythm.cpp host/player/fusion.cpp host/player/lamour.cpp host/player/adagio.cpp host/player/bells.cpp tests/test_player_audio.cpp host/player/player.hpp host/player/dance.hpp host/player/rhythm.hpp host/player/fusion.hpp host/player/lamour.hpp host/player/adagio.hpp host/player/bells.hpp $(OUT)/font.o $(OUT)/pwm.o host/player/Makefile
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) host/player/audio.cpp host/player/show.cpp host/player/theatre.cpp host/player/dance.cpp host/player/rhythm.cpp host/player/fusion.cpp host/player/lamour.cpp host/player/adagio.cpp host/player/bells.cpp tests/test_player_audio.cpp $(OUT)/font.o $(OUT)/pwm.o -o $@ $(LDLIBS)
.PHONY: audio-check
audio-check: $(OUT)/test-player $(OUT)/test-audio
	$(OUT)/test-player
	$(OUT)/test-audio

$(OUT)/test-video.mkv: host/player/Makefile | $(OUT)
	ffmpeg -v error -y -f lavfi -i "nullsrc=s=80x16:r=10:d=30,geq=lum='mod(X*3+Y*7+N*17,256)':cb=128:cr=128" -c:v ffv1 $@
$(OUT)/test-video: host/player/video.cpp tests/test_player_video.cpp host/player/player.hpp host/player/dance.hpp host/player/rhythm.hpp host/player/fusion.hpp host/player/lamour.hpp host/player/adagio.hpp host/player/bells.hpp $(OUT)/test-video.mkv host/player/Makefile
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) host/player/video.cpp tests/test_player_video.cpp -o $@ $(LDLIBS)

$(OUT)/test-dance: host/player/dance.cpp tests/test_player_dance.cpp host/player/dance.hpp host/player/player.hpp host/player/rhythm.hpp host/player/fusion.hpp host/player/lamour.hpp host/player/adagio.hpp host/player/bells.hpp | $(OUT)
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) host/player/dance.cpp tests/test_player_dance.cpp -o $@
$(OUT)/test-rhythm: host/player/rhythm.cpp tests/test_player_rhythm.cpp host/player/rhythm.hpp host/player/fusion.hpp host/player/lamour.hpp host/player/adagio.hpp host/player/bells.hpp | $(OUT)
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) host/player/rhythm.cpp tests/test_player_rhythm.cpp -o $@

$(OUT)/test-adagio: host/player/adagio.cpp tests/test_player_adagio.cpp host/player/fusion.hpp host/player/lamour.hpp host/player/adagio.hpp host/player/player.hpp | $(OUT)
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) host/player/adagio.cpp tests/test_player_adagio.cpp -o $@
$(OUT)/test-bells: host/player/bells.cpp tests/test_player_bells.cpp host/player/bells.hpp host/player/player.hpp | $(OUT)
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) host/player/bells.cpp tests/test_player_bells.cpp -o $@

$(OUT)/test-fusion: host/player/fusion.cpp tests/test_player_fusion.cpp host/player/fusion.hpp host/player/player.hpp host/player/rhythm.hpp | $(OUT)
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) host/player/fusion.cpp tests/test_player_fusion.cpp -o $@
