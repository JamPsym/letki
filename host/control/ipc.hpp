#pragma once
#include <string>
namespace control::ipc {
// Local, versioned NDJSON. A call opens one connection and returns one reply.
std::string default_socket();
std::string call(const std::string &request, const std::string &socket = {},
                 int timeout_ms = 3000);
// Starts only a missing service. Existing service settings are never changed.
bool ensure_service(const std::string &socket = {}, bool simulate = false,
                    bool autoconnect = true, const std::string &port = {});
} // namespace control::ipc
