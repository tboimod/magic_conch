"""Next-result reservations through the real core, hotkey, selector and API.

Import the existing integration fixture (and its baseline checks), then exercise
the additive API without a desktop-only package global in production code.
"""
from test_room_usage import lua

lua.execute(r'''
package = nil
local api = mod.API
local function finish()
    for i=1,12 do mod:OnUpdate() end
    assert(api.GetState()=="idle")
end
local function reset()
    mod:OnNewRoom()
    mod.Config.enabled=true
    mod.Config.attemptsPerRoom=0
    mod.Config.forcedReply="None"
    mod.Config.timing={shake=1,wait=1,display=3,cooldown=0}
    frame=frame+100
    pressed=false; mod:OnHotkeyInput()
end
local function reserve(kind, guard)
    local ok, token=api.ReserveNextResult("owner",{type=kind},guard)
    assert(ok and type(token)=="number",tostring(token))
    return token
end
local function same(token)
    local value=api.GetNextResultReservation("owner")
    assert(value and value.token==token,"reservation unexpectedly changed")
end
reset()

-- Reservations/previews are detached and have no activation/save side effects.
local before=api.GetCurrentRoomUsage()
local beforeEffects,beforeObserved,beforeNotified,beforeSaves=effects,observed,notified,saves
local afterNext=api.PreviewResult(1)
local options={type="positive"}
local ok,token=api.ReserveNextResult("owner",options)
assert(ok)
options.type="negative"
local read=api.GetNextResultReservation()
assert(read.owner=="owner" and read.options.type=="positive")
read.options.type="neutral"; read.token=0
for i=1,20 do
    assert(api.PreviewResult().type=="positive" and api.PreviewResult().forced)
    assert(api.PreviewResult(0,{}).type=="positive")
    same(token)
end
assert(api.PreviewResult(1).id==afterNext.id and not api.PreviewResult(1).forced)
assert(api.GetCurrentRoomUsage()==before and api.GetState()=="idle")
assert(effects==beforeEffects and observed==beforeObserved and notified==beforeNotified and saves==beforeSaves)
assert(mod.Config.forcedReply=="None")

-- The provider's actual native hotkey consumes exactly one reservation/use.
pressed=true; mod:OnHotkeyInput()
assert(api.GetCurrentRoomUsage()==before+1 and not api.GetNextResultReservation())
mod:OnHotkeyInput(); finish(); mod:OnHotkeyInput()
assert(api.GetCurrentRoomUsage()==before+1 and api.GetLastResult().type=="positive")
pressed=false; mod:OnHotkeyInput()
frame=frame+100
assert(api.TriggerMagicConch("normal").success)
finish()
assert(not api.GetLastResult().forced,"one-use reservation leaked into another activation")

-- Explicit override wins without stealing the next ordinary-use reservation.
reset(); token=reserve("negative")
assert(api.PreviewResult(0,{id="Yes"}).type=="positive"); same(token)
local result=api.TriggerMagicConch("other",{id="Yes"})
assert(result.success and result.pendingResult.type=="positive"); same(token)
finish(); frame=frame+100
result=api.TriggerMagicConch("normal",{})
assert(result.success and result.pendingResult.type=="negative" and result.pendingResult.forced)
assert(not api.GetNextResultReservation()); finish()

-- Invalid/disabled/limited/cooldown/busy activation preserves the reservation.
reset(); token=reserve("neutral"); before=api.GetCurrentRoomUsage()
assert(not api.TriggerMagicConch("invalid",{id="missing"}).success); same(token)
assert(api.GetCurrentRoomUsage()==before)
mod.Config.enabled=false
assert(not api.TriggerMagicConch("disabled").success); same(token)
mod.Config.enabled=true
mod.Config.attemptsPerRoom=before
assert(before>0 and api.TriggerMagicConch("limit").reason=="ROOM_LIMIT"); same(token)
pressed=true; mod:OnHotkeyInput(); pressed=false; mod:OnHotkeyInput()
same(token); assert(api.GetCurrentRoomUsage()==before)
mod.Config.attemptsPerRoom=0
assert(api.TriggerMagicConch("explicit",{id="Yes"}).success); same(token)
assert(not api.TriggerMagicConch("busy").success); same(token)
finish()
assert(api.TriggerMagicConch("cooldown").reason=="COOLDOWN"); same(token)
frame=frame+100
assert(api.TriggerMagicConch("ordinary").success)
assert(not api.GetNextResultReservation()); finish()

-- A new choice made during an animation survives completion for the next use.
reset()
assert(api.TriggerMagicConch("first",{id="Yes"}).success)
token=reserve("negative")
mod:OnUpdate(); mod:OnUpdate()
assert(api.GetState()=="displaying"); same(token)
frame=frame+100; pressed=true; mod:OnHotkeyInput()
assert(api.GetState()=="shaking" and not api.GetNextResultReservation())
finish(); assert(api.GetLastResult().type=="negative")

-- Owners cannot overwrite/clear each other; the same owner can replace a choice.
reset(); token=reserve("positive")
local accepted,reason=api.ReserveNextResult("other",{type="negative"})
assert(not accepted and reason=="RESERVED_BY_OTHER_MOD")
assert(not api.GetNextResultReservation("other") and not api.ClearNextResultReservation("other"))
same(token)
local replacement=reserve("neutral")
assert(replacement~=token and api.PreviewResult().type=="neutral")
assert(api.ClearNextResultReservation("owner") and not api.ClearNextResultReservation("owner"))

-- Owner guards run at the exact read/use boundary, before consumer update order.
local owned=true
token=reserve("negative",function() return owned end)
owned=false
result=api.TriggerMagicConch("lost item before owner update")
assert(result.success and not result.pendingResult.forced and not api.GetNextResultReservation())
finish(); reset()
local throw=false
token=reserve("positive",function() if throw then error("owner unloaded") end return true end)
throw=true
assert(not api.GetNextResultReservation() and not api.PreviewResult().forced)
accepted,reason=api.ReserveNextResult("owner",{type="positive"},function() return false end)
assert(not accepted and reason=="OWNER_UNAVAILABLE")

-- Bad replacement never destroys the previous valid choice or changes state.
token=reserve("neutral"); before=api.GetCurrentRoomUsage()
local invalid={
    {"",{type="positive"}}, {false,{type="positive"}},
    {"owner",false}, {"owner",{}}, {"owner",{unknown=true}},
    {"owner",{type="missing"}}, {"owner",{id="missing"}},
    {"owner",{id="Yes",type="positive"}},
    {"owner",{type="positive",text="\n"}},
    {"owner",{type="positive"},true},
}
for _,case in ipairs(invalid) do
    assert(not api.ReserveNextResult(case[1],case[2],case[3])); same(token)
end
activeRun=false
accepted,reason=api.ReserveNextResult("owner",{type="positive"})
assert(not accepted and reason=="NO_ACTIVE_RUN")
activeRun=true
assert(api.GetCurrentRoomUsage()==before and api.GetState()=="idle")

-- All lifecycle boundaries clear the queue, including Continue. No save stores it.
for _,choice in ipairs({{id="Yes"},{type="neutral",text="Wait here."}}) do
    reset()
    assert(api.ReserveNextResult("owner",choice))
    local forecast=api.PreviewResult()
    result=api.TriggerMagicConch("normal")
    assert(result.success and result.pendingResult.text==forecast.text)
    assert(result.pendingResult.id==forecast.id and result.pendingResult.forced)
    assert(not api.GetNextResultReservation()); finish()
end
for _,boundary in ipairs({"OnNewRoom","OnNewLevel","OnGameExit","Continue","NewRun"}) do
    reset(); reserve("positive")
    if boundary=="Continue" then mod:OnGameStart(true)
    elseif boundary=="NewRun" then mod:OnGameStart(false)
    else mod[boundary](mod) end
    assert(not api.GetNextResultReservation(),"reservation survived "..boundary)
    assert(not saved:find("nextResult") and not saved:find("reservation"))
end
''')
print("PASS: next-result API: real hotkey/API one-shot use, preview isolation, owner isolation, rejected uses, override precedence, live guards and lifecycle cleanup")
