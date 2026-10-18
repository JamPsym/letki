#pragma once
#include "player.hpp"

namespace letki {
// Stateless source-time rendering: seeking never needs a warm-up simulation.
bool dance_style(const std::string &style);
Frame dance(const Feature &, double sourceSeconds, const std::string &style,
            double beatPosition);
} // namespace letki
