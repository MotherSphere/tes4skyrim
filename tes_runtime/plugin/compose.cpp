#include "compose.h"

#include <windows.h>

#include <algorithm>
#include <cctype>
#include <cstdlib>
#include <fstream>
#include <map>
#include <sstream>

#include "log.h"

namespace tesruntime {

namespace {

std::string Lower(std::string s) {
    for (auto& c : s) c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
    return s;
}

int ToInt(const std::string& s) { return std::atoi(s.c_str()); }

Lines JsonLines(const Json& arr) {
    Lines out;
    for (const auto& v : arr.items()) out.push_back(v.asString());
    return out;
}

// (names, body) of a singlefile: the leading count + name list, rest.
void SplitRegistry(const Lines& base, Lines& names, Lines& body) {
    const int n = base.empty() ? 0 : ToInt(base[0]);
    names.assign(base.begin() + 1, base.begin() + 1 + n);
    body.assign(base.begin() + 1 + n, base.end());
}

void AppendWrapped(Lines& out, const Lines& block) {
    out.push_back(std::to_string(block.size()));
    out.insert(out.end(), block.begin(), block.end());
}

}  // namespace

std::vector<Json> LoadFragments(const std::string& dir) {
    std::vector<std::string> files;
    WIN32_FIND_DATAA fd;
    HANDLE h = FindFirstFileA((dir + "\\*.json").c_str(), &fd);
    if (h != INVALID_HANDLE_VALUE) {
        do {
            if (!(fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)) files.emplace_back(fd.cFileName);
        } while (FindNextFileA(h, &fd));
        FindClose(h);
    }
    std::sort(files.begin(), files.end(),
              [](const std::string& a, const std::string& b) { return Lower(a) < Lower(b); });

    std::vector<Json> out;
    for (const auto& fn : files) {
        std::ifstream f(dir + "\\" + fn, std::ios::binary);
        std::stringstream ss;
        ss << f.rdbuf();
        std::string err;
        Json j = Json::Parse(ss.str(), &err);
        if (!j.isObject()) {
            Log("fragment %s: unreadable (%s)", fn.c_str(), err.c_str());
            continue;
        }
        if (j["version"].asInt() != 1) {
            Log("fragment %s: unsupported version %d", fn.c_str(), j["version"].asInt());
            continue;
        }
        Log("fragment %s: %zu animdata, %zu animsetdata (source %s)",
            fn.c_str(), j["animdata"].size(), j["animsetdata"].size(),
            j["source"].asString().c_str());
        out.push_back(std::move(j));
    }
    return out;
}

Lines SplitLines(const std::string& text) {
    Lines out;
    size_t start = 0;
    while (start <= text.size()) {
        size_t nl = text.find('\n', start);
        if (nl == std::string::npos) {
            if (start < text.size()) out.push_back(text.substr(start));
            break;
        }
        size_t end = nl;
        if (end > start && text[end - 1] == '\r') --end;
        out.push_back(text.substr(start, end - start));
        start = nl + 1;
    }
    return out;
}

std::string JoinLines(const Lines& lines) {
    std::string out;
    size_t total = 0;
    for (const auto& l : lines) total += l.size() + 2;
    out.reserve(total);
    for (const auto& l : lines) { out += l; out += "\r\n"; }
    return out;
}

Lines ComposeAnimationData(const Lines& base, const std::vector<Json>& fragments) {
    Lines names, body;
    SplitRegistry(base, names, body);
    std::map<std::string, bool> have;
    for (const auto& n : names) have[Lower(n)] = true;
    Lines newNames, newBody;
    for (const auto& frag : fragments) {
        for (const auto& e : frag["animdata"].items()) {
            const std::string key = Lower(e["project"].asString());
            if (have.count(key)) continue;
            have[key] = true;
            newNames.push_back(e["project"].asString());
            AppendWrapped(newBody, JsonLines(e["clip_block"]));
            if (!e["motion_block"].isNull()) AppendWrapped(newBody, JsonLines(e["motion_block"]));
        }
    }
    Lines out;
    out.push_back(std::to_string(names.size() + newNames.size()));
    out.insert(out.end(), names.begin(), names.end());
    out.insert(out.end(), newNames.begin(), newNames.end());
    out.insert(out.end(), body.begin(), body.end());
    out.insert(out.end(), newBody.begin(), newBody.end());
    return out;
}

Lines ComposeAnimationSetData(const Lines& base, const std::vector<Json>& fragments) {
    Lines names, body;
    SplitRegistry(base, names, body);
    std::map<std::string, bool> have;
    for (const auto& n : names) have[Lower(n)] = true;
    Lines newNames, newBody;
    for (const auto& frag : fragments) {
        for (const auto& e : frag["animsetdata"].items()) {
            const std::string key = Lower(e["entry"].asString());
            if (have.count(key)) continue;
            have[key] = true;
            newNames.push_back(e["entry"].asString());
            const Lines block = JsonLines(e["block"]);
            newBody.insert(newBody.end(), block.begin(), block.end());
        }
    }
    Lines out;
    out.push_back(std::to_string(names.size() + newNames.size()));
    out.insert(out.end(), names.begin(), names.end());
    out.insert(out.end(), newNames.begin(), newNames.end());
    out.insert(out.end(), body.begin(), body.end());
    out.insert(out.end(), newBody.begin(), newBody.end());
    return out;
}

}  // namespace tesruntime
