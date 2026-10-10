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
fontAvailable, fontDraws, nativeDraws = true, {}, {}
Font = function() return {Load=function() end, IsLoaded=function() return fontAvailable end,
    GetLineHeight=function() return 14 end,
    DrawStringUTF8=function(_, text, x, y, color, width, center)
        fontDraws[#fontDraws+1]={text=text,x=x,y=y,color=color,width=width,center=center}
    end} end
Sprite = function() return {Load=function() end, ReplaceSpritesheet=function() end,
    LoadGraphics=function() end, SetFrame=function() end, IsLoaded=function() return true end,
    Render=function() end} end
Vector = function(x,y) return {X=x,Y=y} end
Color = function(...) return {...} end
KColor = Color
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
    GetHUD=function() return {
        ShowItemText=function(_, text, subtitle) nativeDraws[#nativeDraws+1]={text=text,subtitle=subtitle,style=1} end,
        ShowFortuneText=function(_, text) nativeDraws[#nativeDraws+1]={text=text,style=0} end} end,
} end
Isaac = {ConsoleOutput=function() end, GetPlayer=function() return testPlayer end, RenderText=function() end,
    SaveModData=function(_, value) saved=value; saves=saves+1 end,
    LoadModData=function() return saved end}
RegisterMod = function() return {HasData=function() return saved ~= nil end, AddCallback=function() end} end
mod = include("magic_conch_core")
local unavailable, reason = modules.magic_conch_api.PreviewResult()
assert(unavailable == nil and reason == "API_NOT_READY")
assert(modules.magic_conch_api.GetCurrentRoomUsage() == nil)
assert(modules.magic_conch_api.GetResultPosition() == nil)
assert(not modules.magic_conch_api.SetResultPosition(1,2))
assert(not modules.magic_conch_api.ResetResultPosition())
assert(not modules.magic_conch_api.TriggerMagicConch().success)
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
local noUsage, usageError = mod.API.GetCurrentRoomUsage()
assert(noUsage == nil and usageError == "NO_ACTIVE_RUN")
assert(mod.API.TriggerMagicConch().reason == "NO_ACTIVE_RUN")
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

-- Public count and placement APIs: detached results, validation and persistence.
local api = mod.API
assert(api.GetCurrentRoomUsage() == 10)
assert(api.GetResultPosition().mode == "hud" and api.GetResultPosition().x == nil)
local savesBeforePosition, savedBeforePosition = saves, saved
for _, invalid in ipairs({-1, 10001, "20", false, {}, 0/0, math.huge}) do
    local ok, err = api.SetResultPosition(invalid, 40)
    assert(not ok and err == "INVALID_POSITION")
    assert(not api.SetResultPosition(40, invalid))
end
assert(not api.SetResultPosition(nil,40) and not api.SetResultPosition(40,nil))
assert(saves == savesBeforePosition and saved == savedBeforePosition)
assert(api.SetResultPosition(125.5,60))
local location=api.GetResultPosition()
assert(location.mode == "custom" and location.x == 125.5 and location.y == 60 and location.anchor == "top_left")
location.x=999
assert(api.GetResultPosition().x == 125.5 and api.GetCurrentRoomUsage() == 10)
assert(require("json").decode(saved).config.resultPosition.x == 125.5)
mod:OnGameExit(); mod:OnGameStart(true)
assert(api.GetResultPosition().x == 125.5 and api.GetCurrentRoomUsage() == 10)
mod.Config.timing={shake=1,wait=1,display=3,cooldown=0}

-- Invalid forced responses leave the count, cooldown, effects and state untouched.
frame=frame+100
local countBefore, savesBefore, effectsBefore = api.GetCurrentRoomUsage(), saves, effects
for _, options in ipairs({false, "positive", {foo=1}, {id="unknown"}, {id=7}, {id="Yes",type="positive"},
    {id="Yes",text="x"}, {text="x"}, {type="bad"}, {type=false}, {type="positive",text=""},
    {type="positive",text="   "}, {type="positive",text="a\nb"}, {type="positive",text=123},
    {type="positive",text=string.char(255)}, {type="positive",text=string.rep("a",257)}}) do
    local preview, why=api.PreviewResult(0, options)
    assert(preview == nil and type(why) == "string")
    local result=api.TriggerMagicConch("test", options)
    assert(not result.success and result.reason == why)
end
assert(api.GetCurrentRoomUsage() == countBefore and saves == savesBefore and effects == effectsBefore)
assert(api.GetState() == "idle")
assert(api.PreviewResult(0, {}).id == api.PreviewResult().id)
assert(api.PreviewResult(0, {type="neutral",text=string.rep("a",256)}).forced)

-- Per-call overrides win over global forcedReply without changing it.
mod.Config.forcedReply="Negative"
local forced=api.PreviewResult(0,{type="Positive"})
assert(forced.type == "positive" and forced.id and forced.forced)
assert(api.PreviewResult(0,{id="Yes"}).text == "Yes.")
mod.Config.language="KR"
assert(api.PreviewResult(0,{id="Yes"}).text == "좋아.")
mod.Config.language="EN"
assert(mod.Config.forcedReply == "Negative" and api.PreviewResult().type == "negative")

-- All override variants execute normally and consume exactly one use.
local function finish()
    for tick=1,6 do mod:OnUpdate() end
    assert(api.GetState() == "idle")
end
for _, options in ipairs({{type="positive"}, {id="Yes"}}) do
    frame=frame+100
    local preview, count=api.PreviewResult(0, options), api.GetCurrentRoomUsage()
    local result=api.TriggerMagicConch(nil, options)
    assert(result.success and result.pendingResult.type == preview.type and result.pendingResult.id == preview.id)
    assert(result.pendingResult.forced and api.GetCurrentRoomUsage() == count+1)
    finish()
    assert(api.GetLastResult().id == preview.id and api.GetLastResult().forced)
end
assert(mod.Config.forcedReply == "Negative")
mod.Config.forcedReply="None"

-- Custom response: caller mutation, callback isolation, real render coordinates,
-- one renderer per result, settings snapshot, lifetime and normal counter behavior.
local callbackResult
api.RegisterCallback(function(result) result.text="corrupt"; result.position.x=999 end, "mutating consumer")
api.RegisterCallback(function(result) callbackResult=result end, "second consumer")
local options={type="neutral",text="이번에는 기다려."}
local preview=api.PreviewResult(0, options)
local count, nativeBefore=api.GetCurrentRoomUsage(), #nativeDraws
mod.Config.displayStyle=1
frame=frame+100
local activation=api.TriggerMagicConch("custom test",options)
assert(activation.success and activation.pendingResult.text == preview.text and activation.pendingResult.id == nil)
assert(api.GetCurrentRoomUsage() == count+1)
activation.pendingResult.text="corrupt"; activation.pendingResult.position.x=999; options.text="corrupt"
assert(not api.TriggerMagicConch("busy",{id="No"}).success and api.GetCurrentRoomUsage() == count+1)
api.SetResultPosition(222,77); mod.Config.displayStyle=0
local drawsBefore=#fontDraws
mod:OnRender(); mod:OnUpdate(); mod:OnRender()
assert(#fontDraws == drawsBefore, "result rendered before reveal")
mod:OnUpdate(); mod:OnRender()
assert(#fontDraws == drawsBefore+4 and #nativeDraws == nativeBefore)
local main, subtitle=fontDraws[drawsBefore+2],fontDraws[drawsBefore+4]
assert(main.text == preview.text and main.x == 125.5 and main.y == 60 and main.width == 0)
assert(subtitle.text == "[neutral]" and subtitle.x == 125.5 and subtitle.y == 76)
assert(callbackResult.text == preview.text and callbackResult.position.x == 125.5 and callbackResult.forced)
assert(api.GetLastResult().text == preview.text and api.GetLastResult().position.x == 125.5)
local last=api.GetLastResult(); last.text="corrupt"; last.position.x=999
assert(api.GetLastResult().text == preview.text and api.GetLastResult().position.x == 125.5)
for tick=1,3 do mod:OnUpdate() end
mod:OnRender(); assert(#fontDraws == drawsBefore+4, "result outlived display timer")
mod:OnUpdate()

-- A future custom result uses the new position/style; entering a room clears it.
frame=frame+100
assert(api.TriggerMagicConch("next",{id="No"}).success)
mod:OnUpdate(); mod:OnUpdate(); mod:OnRender()
assert(#fontDraws == drawsBefore+6 and fontDraws[#fontDraws].x == 222 and fontDraws[#fontDraws].y == 77)
local latestDraws=#fontDraws
mod:OnNewRoom(); mod:OnRender(); assert(#fontDraws == latestDraws)

-- Both limit and disabled gates remain in force for forced responses.
mod.Config.attemptsPerRoom=api.GetCurrentRoomUsage()
frame=frame+100
assert(api.TriggerMagicConch("limited",{id="No"}).reason == "ROOM_LIMIT")
assert(api.GetCurrentRoomUsage() == mod.Config.attemptsPerRoom)
mod.Config.attemptsPerRoom=0; mod.Config.enabled=false
assert(not api.TriggerMagicConch("disabled",{id="No"}).success)
mod.Config.enabled=true

-- Font failure is an explicit native fallback; returning to native HUD persists.
fontAvailable=false
nativeBefore=#nativeDraws
assert(api.TriggerMagicConch("font fallback",{id="Yes"}).success)
mod:OnUpdate(); mod:OnUpdate(); mod:OnRender()
assert(#nativeDraws == nativeBefore+1 and api.GetLastResult().position.mode == "hud")
assert(#fontDraws == latestDraws)
finish(); fontAvailable=true
assert(api.ResetResultPosition())
assert(api.GetResultPosition().mode == "hud" and require("json").decode(saved).config.resultPosition == false)
for _, style in ipairs({0,1}) do
    mod.Config.displayStyle=style; frame=frame+100; nativeBefore=#nativeDraws
    assert(api.TriggerMagicConch("native",{id="Yes"}).success)
    mod:OnUpdate(); mod:OnUpdate(); mod:OnRender()
    assert(#nativeDraws == nativeBefore+1 and nativeDraws[#nativeDraws].style == style)
    assert(#fontDraws == latestDraws)
    finish()
end
-- Forced types reach the existing player effects, not only the result callback.
local pickedUp, happy, sad = 0, 0, 0
testPlayer={AnimatePickup=function() pickedUp=pickedUp+1 end,
    AnimateHappy=function() happy=happy+1 end, AnimateSad=function() sad=sad+1 end}
for _, kind in ipairs({"positive", "negative", "neutral"}) do
    frame=frame+100
    assert(api.TriggerMagicConch("effects",{type=kind}).success)
    finish()
    assert(api.GetLastResult().type == kind)
end
assert(pickedUp == 3 and happy == 1 and sad == 1)
testPlayer=nil
''')
print("PASS: real core/API/config integration; hotkey + API increment once; rejected use and preview do not increment")
print("PASS: room/floor/dimension revisit, immediate JSON save, module reload/continue, old count migration, new-run reset")
print("PASS: PreviewResult offsets, errors, settings, busy/disabled/limit behavior, no state/effects/save/observer/callback changes, actual trigger match")
print("PASS: public count, persisted result position/reset, per-call type/ID/text overrides, input validation and config isolation")
print("PASS: real renderer coordinates, UTF-8 text, reveal/expiry/room reset, native styles/font fallback and detached callbacks/results")
