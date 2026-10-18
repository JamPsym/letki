#pragma once
#include "player.hpp"

namespace letki {
bool adagio_style(const std::string &style);
// Stateless source-audio-time renderer; beatPosition is an authored clock.
Frame adagio(const Feature &, double sourceSeconds, const std::string &style,
             double beatPosition);
} // namespace letki
