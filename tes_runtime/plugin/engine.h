// The engine calls both gun routing and limb severing make, resolved once.
//
// Every entry point is an Address Library ID (ids.h); nothing here is a raw
// RVA. Papyrus natives are called the way the VM calls them: the VM pointer
// the SKSE Papyrus interface hands over, a stack id of 0, then the script
// arguments. Forms are resolved by (plugin-local FormID, file name) through
// the engine's own load order (the Game.GetFormFromFile native), so the
// sidecars never assume a load position.

#pragma once

#include <cstddef>
#include <cstdint>
#include <string>

#include "skse_abi.h"

namespace tesruntime {

template <typename T>
T VCall(void* obj, std::size_t slot) {
    return reinterpret_cast<T>((*reinterpret_cast<void***>(obj))[slot]);
}

template <typename T>
T& At(void* base, std::size_t off) {
    return *reinterpret_cast<T*>(static_cast<char*>(base) + off);
}

// TESForm layout the plugin reads.
constexpr std::size_t kFormID = 0x14;
constexpr std::size_t kFormType = 0x1a;
constexpr std::uint8_t kFormTypeWeapon = 0x29;
constexpr std::uint8_t kFormTypeActor = 0x3e;

// TESObjectREFR / Actor layout the plugin reads.
constexpr std::size_t kRefCount = 0x28;        // BSHandleRefObject, low 10 bits
constexpr std::size_t kActorValueOwner = 0xb8;
constexpr std::size_t kVtGet3D = 0x70;
constexpr std::size_t kVtGetObjectByName = 0x2a;
constexpr int kActorValueHealth = 0x18;

// NiAVObject / NiNode layout.
constexpr std::size_t kVtAsNode = 3;
constexpr std::size_t kVtAsGeometry = 9;
constexpr std::size_t kNodeChildren = 0x118;
constexpr std::size_t kNodeChildCount = 0x122;
constexpr std::size_t kWorldTranslate = 0xa0;

using FixedStringCtorFn = void* (*)(void* self, const char* text);
using FixedStringDtorFn = void (*)(void* self);
using GetFormFromFileFn = void* (*)(void* vm, std::uint32_t stack, void* tag,
                                    std::int32_t formID, void* fileName);
using PlaceAtMeFn = void* (*)(void* vm, std::uint32_t stack, void* self, void* form,
                              std::int32_t count, bool persist, bool disabled);
using SetPositionFn = void (*)(void* vm, std::uint32_t stack, void* self,
                               float x, float y, float z);
using ImpulseFn = void (*)(void* vm, std::uint32_t stack, void* self,
                           float x, float y, float z, float magnitude);
using LookupByHandleFn = void* (*)(std::uint32_t* handle, void** out);
using LookupFormFn = void* (*)(std::uint32_t formID);
using GetActorValueFn = float (*)(void* owner, int av);

// A BSFixedString built and torn down by the engine's own constructor and
// destructor, so the interned pool is never touched by hand.
struct FixedString {
    void* ptr = nullptr;
    explicit FixedString(const char* text);
    ~FixedString();
    FixedString(const FixedString&) = delete;
    FixedString& operator=(const FixedString&) = delete;
};

struct EngineApi {
    FixedStringCtorFn fixedStringCtor = nullptr;
    FixedStringDtorFn fixedStringDtor = nullptr;
    GetFormFromFileFn getFormFromFile = nullptr;
    LookupFormFn      lookupForm = nullptr;
    PlaceAtMeFn       placeAtMe = nullptr;
    SetPositionFn     setPosition = nullptr;
    ImpulseFn         applyImpulse = nullptr;
    LookupByHandleFn  lookupByHandle = nullptr;
    void*             vm = nullptr;
    SKSETaskInterface* task = nullptr;
};

extern EngineApi g_api;

// Resolves the shared entry points; false when the fixed-string pair or the
// form lookup is missing, in which case nothing that needs forms installs.
bool ResolveEngine();

// The form (`local`, `file`) names in the running load order, or null.
void* FormFromFile(std::uint32_t local, const std::string& file);

// A ref's world translate as three floats (false when it has no 3D).
bool RefPosition(void* ref, float* out);

// <exe dir>\Data\SKSE\Plugins\TESRuntime
std::string SidecarDir();

// Every *.<suffix> sidecar under SidecarDir(), parsed (unreadable ones are
// logged and skipped). `suffix` is e.g. "bodyparts.json".
void ForEachSidecar(const char* suffix,
                    void (*visit)(const std::string& name, const class Json& doc));

// Releases a reference LookupReferenceByHandle handed out.
void ReleaseRef(void* ref);

// Drops a heap TaskDelegate onto the game's main-thread task queue.
void RunOnMainThread(TaskDelegate* task);

}  // namespace tesruntime
