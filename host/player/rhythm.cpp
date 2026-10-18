#include "rhythm.hpp"
#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace letki {
void Rhythm::validate() const {
  if (!std::isfinite(bpm) || bpm < 30 || bpm > 300 ||
      !std::isfinite(offset))
    throw std::runtime_error("Rhythm requires finite offset and BPM in 30..300");
  for (size_t i = 0; i < anchors.size(); ++i) {
    const auto &a = anchors[i];
    if (!std::isfinite(a.at) || !std::isfinite(a.beat) || a.at < 0 ||
        a.beat < 0)
      throw std::runtime_error("Rhythm anchors require finite nonnegative time/beat");
    if (!i)
      continue;
    const auto &p = anchors[i - 1];
    if (a.at <= p.at || a.beat <= p.beat)
      throw std::runtime_error("Rhythm anchor time and beat must strictly increase");
    const double tempo = (a.beat - p.beat) / (a.at - p.at) * 60;
    if (!std::isfinite(tempo) || tempo < 30 || tempo > 300)
      throw std::runtime_error("Rhythm anchor tempo must be in 30..300 BPM");
  }
}

double Rhythm::position(double seconds) const {
  if (!std::isfinite(seconds))
    throw std::runtime_error("Rhythm source time must be finite");
  // With no anchors offset is the source time of beat zero. A lone anchor
  // replaces that origin; multiple anchors replace both origin and tempo.
  if (anchors.empty())
    return (seconds - offset) * (bpm / 60);
  if (anchors.size() == 1)
    return anchors.front().beat + (seconds - anchors.front().at) * (bpm / 60);
  auto right = std::upper_bound(
      anchors.begin(), anchors.end(), seconds,
      [](double t, const BeatAnchor &a) { return t < a.at; });
  // Endpoint extrapolation uses the nearest authored segment, preserving
  // continuity and tempo outside the covered recording interval.
  if (right == anchors.begin())
    ++right;
  else if (right == anchors.end())
    --right;
  const auto &a = *(right - 1), &b = *right;
  return a.beat + (seconds - a.at) * ((b.beat - a.beat) / (b.at - a.at));
}
double Rhythm::time(double beat) const {
  if (!std::isfinite(beat))
    throw std::runtime_error("Rhythm beat position must be finite");
  if (anchors.empty())
    return offset + beat * (60 / bpm);
  if (anchors.size() == 1)
    return anchors.front().at + (beat - anchors.front().beat) * (60 / bpm);
  auto right = std::upper_bound(
      anchors.begin(), anchors.end(), beat,
      [](double b, const BeatAnchor &a) { return b < a.beat; });
  if (right == anchors.begin())
    ++right;
  else if (right == anchors.end())
    --right;
  const auto &a = *(right - 1), &b = *right;
  return a.at + (beat - a.beat) * ((b.at - a.at) / (b.beat - a.beat));
}
} // namespace letki
