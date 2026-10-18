#pragma once
#include "player.hpp"
namespace letki {
bool lamour_style(const std::string &style);
Frame lamour(const Media &, const Rhythm &, double seconds, const std::string &style);
}
