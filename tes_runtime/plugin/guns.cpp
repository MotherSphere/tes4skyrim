#include "guns.h"

#include <intrin.h>

#include <cstdlib>
#include <memory>
#include <string>
#include <unordered_map>
#include <vector>

#include "addresses.h"
#include "engine.h"
#include "hook.h"
#include "ids.h"
#include "json.h"
#include "log.h"

namespace tesruntime {

namespace {

constexpr int kGunHandType = 13;
// The engine's interned animation string table (id 11437): iRightHandType
// sits at +0x390, iLeftHandType at +0x388 (0x1dfc20 on 1.6.659).
constexpr std::size_t kTableRightHandType = 0x390;

struct GunProfile {
    int cls = 0, reload = 0, attack = 0, clipSize = 0, automatic = 0;
};

struct PendingGun {
    std::uint32_t local = 0;
    std::string file;
    GunProfile profile;
};

using HandTypeFn = int (*)(void* form);
using SetVarIntFn = bool (*)(void* graph, void* name, int value);
using TableFn = void* (*)();

HandTypeFn  g_origHandType = nullptr;
SetVarIntFn g_origSetVar = nullptr;
TableFn     g_table = nullptr;

std::vector<PendingGun> g_pending;
std::unordered_map<void*, GunProfile> g_guns;
void* g_lastGun = nullptr;
// Callers that keep the vanilla answer: the attack IDLE tree conditions on
// GetEquippedItemType == 12 to send crossbowAttackStart, and scripts expect
// the vanilla range.
std::uintptr_t g_vanillaCallers[2] = {0, 0};

bool WantsVanillaType(std::uintptr_t ret) {
    for (std::uintptr_t fn : g_vanillaCallers) {
        if (fn && ret > fn && ret < fn + ids::kEquippedItemTypeSpan) return true;
    }
    return false;
}

// Interned once; the graph setter takes the BSFixedString by reference.
std::unique_ptr<FixedString> g_varNames[5];
const char* const kVarNames[5] = {"iGunClass", "iGunReload", "iGunAttack",
                                  "iGunClipSize", "iGunAuto"};

void LoadSidecar(const std::string& name, const Json& doc) {
    if (doc["version"].asInt() != 1) {
        Log("guns: %s has version %d, want 1", name.c_str(), doc["version"].asInt());
        return;
    }
    int n = 0;
    for (const auto& kv : doc["guns"].fields()) {
        PendingGun g;
        g.local = static_cast<std::uint32_t>(std::strtoul(kv.first.c_str(), nullptr, 16));
        g.file = kv.second["file"].asString();
        g.profile.cls = kv.second["class"].asInt();
        g.profile.reload = kv.second["reload"].asInt();
        g.profile.attack = kv.second["attack"].asInt(-1);
        g.profile.clipSize = kv.second["clip_size"].asInt();
        g.profile.automatic = kv.second["auto"].asInt();
        if (g.profile.attack < 0) g.profile.attack = 0;
        g_pending.push_back(std::move(g));
        ++n;
    }
    Log("guns: %s: %d guns", name.c_str(), n);
}

int HandTypeHook(void* form) {
    const int v = g_origHandType(form);
    if (!form || g_guns.empty()) return v;
    if (At<std::uint8_t>(form, kFormType) != kFormTypeWeapon) return v;
    auto it = g_guns.find(form);
    if (it == g_guns.end()) return v;
    if (WantsVanillaType(reinterpret_cast<std::uintptr_t>(_ReturnAddress()))) return v;
    g_lastGun = form;
    return kGunHandType;
}

bool SetVarHook(void* graph, void* name, int value) {
    const bool r = g_origSetVar(graph, name, value);
    if (value != kGunHandType || !g_lastGun || !name) return r;
    void* table = g_table();
    if (!table || At<void*>(name, 0) != At<void*>(table, kTableRightHandType)) return r;
    auto it = g_guns.find(g_lastGun);
    if (it == g_guns.end()) return r;
    const GunProfile& p = it->second;
    const int values[5] = {p.cls, p.reload, p.attack, p.clipSize, p.automatic};
    for (int i = 0; i < 5; ++i) {
        if (!g_varNames[i]) g_varNames[i].reset(new FixedString(kVarNames[i]));
        g_origSetVar(graph, &g_varNames[i]->ptr, values[i]);
    }
    return r;
}

}  // namespace

bool InstallGuns() {
    ForEachSidecar("guns.json", LoadSidecar);
    if (g_pending.empty()) {
        Log("guns: no gun sidecars; routing not installed");
        return false;
    }
    const std::uintptr_t handType = Resolve("GetHandAnimType", ids::kHandAnimType, nullptr);
    const std::uintptr_t setVar = Resolve("BShkbAnimationGraph::SetVariableInt", ids::kGraphSetVariableInt, nullptr);
    const std::uintptr_t table = Resolve("AnimStringTable", ids::kAnimStringTable, nullptr);
    if (!handType || !setVar || !table) {
        Log("guns: an address is unresolved; routing not installed");
        return false;
    }
    g_origHandType = reinterpret_cast<HandTypeFn>(handType);
    g_origSetVar = reinterpret_cast<SetVarIntFn>(setVar);
    g_table = reinterpret_cast<TableFn>(table);
    g_vanillaCallers[0] = Resolve("GetEquippedItemType(condition)", ids::kEquippedItemTypeCondition, nullptr);
    g_vanillaCallers[1] = Resolve("GetEquippedItemType(papyrus)", ids::kEquippedItemTypeNative, nullptr);
    if (!g_vanillaCallers[0]) {
        Log("guns: the GetEquippedItemType condition is unresolved; routing not installed");
        return false;
    }
    const int a = PatchAllCalls(handType, reinterpret_cast<void*>(&HandTypeHook), "GetHandAnimType");
    const int b = PatchAllCalls(setVar, reinterpret_cast<void*>(&SetVarHook), "SetVariableInt");
    return a > 0 && b > 0;
}

void ResolveGunForms() {
    int n = 0;
    for (const PendingGun& g : g_pending) {
        void* form = FormFromFile(g.local, g.file);
        if (!form) continue;
        g_guns[form] = g.profile;
        ++n;
    }
    Log("guns: %d of %zu guns resolved", n, g_pending.size());
}

}  // namespace tesruntime
