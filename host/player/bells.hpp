#pragma once
#include "player.hpp"

namespace letki {
bool bells_style(const std::string &style);
Frame bells(const Feature &, double source_seconds, const std::string &style);
} // namespace letki
