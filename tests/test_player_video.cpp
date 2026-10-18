#include "player.hpp"
#include <cassert>
#include <iostream>
int main() {
  letki::Video video("build/player/test-video.mkv");
  assert(video.duration() > 29.9 && video.duration() < 30.1);
  auto a = video.image(.2), b = video.image(.8);
  assert(a.width == 80 && a.height == 16 && a.stride >= a.width * 3);
  assert(a.rgb != b.rgb);
  assert(a.rgb.size() >= size_t(a.height * a.stride));
  video.image(28.7);
  assert(video.image(.2).rgb == a.rgb);
  assert(video.image(30.2).rgb == a.rgb);
  bool failed = false;
  try {
    letki::Video missing("/does/not/exist");
  } catch (...) {
    failed = true;
  }
  assert(failed);
  std::cout << "Native PC video: RGB decode, dimensions, backward/forward "
               "seek, looping and invalid input passed.\n";
}
