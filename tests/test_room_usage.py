"""Real core/API/config/selector integration with mocked Isaac UI and disk APIs."""
import json
from pathlib import Path
from lupa.lua53 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
lua = LuaRuntime(unpack_returned_tuples=True)


def plain(value):
    if hasattr(value, "items"):
        return {str(k): plain(v) for k, v in value.items()}
    return value


lua.globals().encode_json = lambda value: json.dumps(plain(value))
lua.globals().decode_json = lambda value: lua.table_from(json.loads(value), recursive=True)
lua.globals().source = lambda name: (ROOT / (name + ".lua")).read_text(encoding="utf-8")
lua.execute(r'''
package.preload.json = function() return {encode=encode_json, decode=decode_json} end
modules = {
    magic_conch_mcm = {Setup=function() end},
    magic_conch_render = {Render=function() end},
    magic_conch_rng_test = {Install=function() end},
}
function include(name)
    if not modules[name] then modules[name] = assert(load(source(name)))() end
    return modules[name]
end
Keyboard = {KEY_N=78}
Options = {Language="en"}
ModCallbacks = {MC_POST_UPDATE=1, MC_POST_RENDER=2, MC_POST_GAME_STARTED=3,
    MC_POST_NEW_LEVEL=4, MC_POST_NEW_ROOM=5, MC_PRE_GAME_EXIT=6}
SoundEffect = {SOUND_COIN_SLOT=1, SOUND_BOSS2INTRO_ERRORBUZZ=2}
Font = function() return {Load=function() end} end
SFXManager = function() return {Play=function() effects=effects+1 end} end
Input = {IsButtonPressed=function() return pressed end}
frame, pressed, saves = 100, false, 0
activeRun, effects, observed, notified = true, 0, 0, 0
ctx = {startSeed=123456789, stage=1, stageType=0, dimension=0, roomIndex=84,
    roomListIndex=0, spawnSeed=111, decorationSeed=444}
local function descriptor()
    return {Data={Type=1}, SafeGridIndex=ctx.roomIndex, GridIndex=ctx.roomIndex,
        ListIndex=ctx.roomListIndex, SpawnSeed=ctx.spawnSeed, DecorationSeed=ctx.decorationSeed}
end
local level = {
    GetStage=function() return ctx.stage end,
    GetStageType=function() return ctx.stageType end,
    GetCurrentRoomIndex=function() return currentTile or ctx.roomIndex end,
    GetCurrentRoomDesc=descriptor,
    GetRoomByIdx=function(_, index, dimension)
        if index == ctx.roomIndex and dimension == ctx.dimension then return descriptor() end
        return {Data=nil}
    end,
}
Game = function() return {
    GetSeeds=function() return {GetStartSeed=function() return ctx.startSeed end} end,
    GetLevel=function() return level end,
    GetRoom=function() return {GetSpawnSeed=function() return ctx.spawnSeed end,
        GetDecorationSeed=function() return ctx.decorationSeed end} end,
    GetFrameCount=function() return frame end, IsPaused=function() return false end,
    GetNumPlayers=function() return activeRun and 1 or 0 end,
    ShakeScreen=function() effects=effects+1 end,
    GetHUD=function() return {ShowItemText=function() end, ShowFortuneText=function() end} end,
} end
Isaac = {ConsoleOutput=function() end, GetPlayer=function() return nil end,
    SaveModData=function(_, value) saved=value; saves=saves+1 end,
    LoadModData=function() return saved end}
RegisterMod = function() return {HasData=function() return saved ~= nil end, AddCallback=function() end} end
mod = include("magic_conch_core")
local unavailable, reason = modules.magic_conch_api.PreviewResult()
assert(unavailable == nil and reason == "API_NOT_READY")
mod:OnGameStart(false)
local config, lang, random = modules.magic_conch_config, modules.magic_conch_lang, modules.magic_conch_random
mod.Config.language, mod.Config.attemptsPerRoom = "EN", 2
assert(mod:GetCurrentRoomUsage() == 0)
local first = lang.getRandomString(mod.Config)
mod.RNGDiagnostics = {Observe=function() observed=observed+1 end}
mod.API.RegisterCallback(function() notified=notified+1 end, "preview test")
local savedBefore, savesBefore, stateBefore = saved, saves, mod.API.GetState()
local preview = mod.API.PreviewResult()
assert(preview.id == first.id and preview.type == first.type and preview.text == first.text)
assert(preview.usageCount == 0 and preview.useNumber == 1 and preview.offset == 0)
for offset=0,20 do
    local context = lang.getRandomContext()
    context.usageCount = offset
    local expected, actual = lang.sample(mod.Config, context), mod.API.PreviewResult(offset)
    assert(actual.id == expected.id and actual.text == expected.text and actual.type == expected.type)
    assert(actual.usageCount == offset and actual.useNumber == offset+1 and actual.offset == offset)
end
preview.id, preview.text, preview.type = "changed", "changed", "changed"
assert(mod.API.PreviewResult().id == first.id, "caller mutated the actual response")
for _, invalid in ipairs({-1, 0.5, "1", false, {}, 0/0, math.huge, 1000001}) do
    local value, err = mod.API.PreviewResult(invalid)
    assert(value == nil and err == "INVALID_OFFSET")
end
assert(mod.API.PreviewResult(1000000).usageCount == 1000000)
activeRun=false
local value, err = mod.API.PreviewResult()
assert(value == nil and err == "NO_ACTIVE_RUN")
activeRun=true
mod.Config.enabled=false
assert(mod.API.PreviewResult().id == first.id)
mod.Config.enabled=true
mod.Config.forcedReply="Negative"
assert(mod.API.PreviewResult().type == "negative")
mod.Config.forcedReply="None"
assert(mod.API.PreviewResult().id == first.id)
assert(saved == savedBefore and saves == savesBefore and mod.API.GetState() == stateBefore)
assert(effects == 0 and observed == 0 and notified == 0 and mod.API.GetLastResult() == nil)
currentTile = ctx.roomIndex+1
assert(lang.getRandomString(mod.Config).id == first.id, "room tile changed the canonical identity")
currentTile = nil
for i=1,10 do assert(lang.getRandomString(mod.Config).id == first.id) end
assert(mod:GetCurrentRoomUsage() == 0, "preview consumed a use")

-- Hotkey activation commits once; hold/busy/spam/rejection never consumes a use.
pressed=true
mod:OnHotkeyInput()
assert(mod:GetCurrentRoomUsage() == 1)
assert(observed == 1 and mod.API.PreviewResult().usageCount == 1)
local blob = require("json").decode(saved)
local roomKey = random.RoomKey(random.Capture())
assert(blob.runtime.roomUsageCount[roomKey].count == 1, "not saved immediately")
mod:OnHotkeyInput()
assert(mod:GetCurrentRoomUsage() == 1)
assert(not mod.API.TriggerMagicConch("test").success)
assert(mod:GetCurrentRoomUsage() == 1)
pressed=false; mod:OnHotkeyInput()
mod:OnNewRoom()
frame=1
assert(not mod.API.TriggerMagicConch("test").success)
assert(mod:GetCurrentRoomUsage() == 1)
frame=200
local second = lang.getRandomString(mod.Config)
local predictedSecond = mod.API.PreviewResult()
local result = mod.API.TriggerMagicConch("test")
assert(result.success and result.pendingResult.text == second.text and result.pendingResult.type == second.type)
assert(result.pendingResult.text == predictedSecond.text and result.pendingResult.type == predictedSecond.type)
assert(mod:GetCurrentRoomUsage() == 2, "API must increment exactly once")
assert(mod.API.PreviewResult().usageCount == 2, "limit must not consume/block a mathematical preview")
mod:OnNewRoom()
frame=300
assert(not mod.API.TriggerMagicConch("test").success, "API bypassed attemptsPerRoom")
assert(mod:GetCurrentRoomUsage() == 2)
pressed=true; mod:OnHotkeyInput(); pressed=false; mod:OnHotkeyInput()
assert(mod:GetCurrentRoomUsage() == 2, "failed hotkey consumed a use")

-- Rooms, dimensions and floors own independent counters; revisit restores counts.
for _, field in ipairs({"roomIndex", "dimension", "stage", "stageType", "spawnSeed", "decorationSeed", "roomListIndex"}) do
    local old = ctx[field]
    ctx[field] = old+1
    mod:OnNewLevel(); mod:OnNewRoom()
    assert(mod:GetCurrentRoomUsage() == 0, "counter leaked across "..field)
    frame=frame+100
    assert(mod.API.TriggerMagicConch("test").success)
    assert(mod:GetCurrentRoomUsage() == 1)
    ctx[field] = old
    mod:OnNewLevel(); mod:OnNewRoom()
    assert(mod:GetCurrentRoomUsage() == 2, "revisit lost count for "..field)
end
-- Continue reloads a JSON snapshot, not a reference to the in-memory table.
mod:OnGameExit()
local beforeContinue = lang.getRandomString(mod.Config)
modules.magic_conch_core = nil
mod = include("magic_conch_core")
mod:OnGameStart(true)
assert(mod:GetCurrentRoomUsage() == 2)
assert(lang.getRandomString(mod.Config).id == beforeContinue.id)
assert(mod.API.PreviewResult().id == beforeContinue.id and mod.API.PreviewResult().usageCount == 2)

-- One-time migration of old room keys, including the old numeric format.
for _, entry in ipairs({5, {count=5, lastType="positive", lastResponse="saved reply"}}) do
    local oldKey = random.LegacyRoomKey(random.Capture())
    config.SaveRuntime(mod, {roomUsageCount={[oldKey]=entry}})
    mod:OnGameStart(true)
    assert(mod:GetCurrentRoomUsage() == 5)
    mod:OnNewRoom()
    local runtime = config.LoadRuntime(mod)
    assert(runtime.roomUsageCount[oldKey] == nil and runtime.roomUsageCount[roomKey] ~= nil)
end
-- Unlimited use works on API; brand-new runs clear counters.
mod.Config.attemptsPerRoom=0
frame=frame+100
assert(mod.API.TriggerMagicConch("test").success and mod:GetCurrentRoomUsage() == 6)
mod:OnGameExit()
mod:OnGameStart(false)
assert(mod:GetCurrentRoomUsage() == 0)
-- Consume a previewed sequence through the public activation path, on one visit.
-- Complete the animation after each activation so the real state machine runs.
mod.Config.attemptsPerRoom=0
mod.Config.timing={shake=1,wait=1,display=1,cooldown=0}
local forecast={}
for offset=0,9 do forecast[offset]=mod.API.PreviewResult(offset) end
for usage=0,9 do
    frame=frame+100
    local activation=mod.API.TriggerMagicConch("preview test")
    assert(activation.success and activation.pendingResult.text == forecast[usage].text
        and activation.pendingResult.type == forecast[usage].type)
    for tick=1,4 do mod:OnUpdate() end
    assert(mod.API.GetState() == "idle" and mod:GetCurrentRoomUsage() == usage+1)
    assert(mod.API.GetLastResult().text == forecast[usage].text)
end
''')
print("PASS: real core/API/config integration; hotkey + API increment once; rejected use and preview do not increment")
print("PASS: room/floor/dimension revisit, immediate JSON save, module reload/continue, old count migration, new-run reset")
print("PASS: PreviewResult offsets, errors, settings, busy/disabled/limit behavior, no state/effects/save/observer/callback changes, actual trigger match")
