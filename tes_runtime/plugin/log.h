// Plugin log, written to Documents\My Games\Skyrim Special Edition\SKSE\
// TESRuntime.log so it sits alongside the Papyrus logs the project reads.

#pragma once

#include <string>

namespace tesruntime {

// The SKSE log folder with a trailing backslash, or "" when Documents is
// unknown; every file the plugin writes for a human goes here.
std::wstring LogDir();
void OpenLog();
void Log(const char* fmt, ...);

}  // namespace tesruntime
