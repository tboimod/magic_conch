"""Local Lua 5.3 checks. The RNG shim tests plumbing, NOT Isaac's RNG quality.

Run: python tests/test_rng_diagnostics.py  (requires lupa)
Native RNG evidence must come from `mc test` inside Isaac and log.txt.
"""
from pathlib import Path
import tempfile
import json
import math

from aggregate_room_log import parse_log

from lupa.lua53 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
lua = LuaRuntime(unpack_returned_tuples=True)
lua.execute(r'''
context = { startSeed = 123456789, roomIndex = 84, usageCount = 4, roomFrame = 1 }
fixtureRooms = {
    { SafeGridIndex = 84, GridIndex = 84, ListIndex = 0, SpawnSeed = 111, DecorationSeed = 444, Data = {Type = 1}, VisitedCount = 1 },
    { SafeGridIndex = 85, GridIndex = 85, ListIndex = 1, SpawnSeed = 222, DecorationSeed = 555, Data = {Type = 2}, VisitedCount = 0 },
    { SafeGridIndex = 97, GridIndex = 97, ListIndex = 2, SpawnSeed = 333, DecorationSeed = 666, Data = {Type = 1}, VisitedCount = 0 },
}
Options = { Language = "en" }
ModCallbacks = { MC_EXECUTE_CMD = 22, MC_POST_RENDER = 2, MC_PRE_GAME_EXIT = 17 }
logs, callbacks = {}, {}
Isaac = {
    DebugString = function(message) logs[#logs + 1] = message end,
    ConsoleOutput = function() end,
}
Game = function() return {
    GetSeeds = function() return { GetStartSeed = function() return context.startSeed end } end,
    GetLevel = function() return {
        GetCurrentRoomIndex = function() return context.roomIndex end,
        GetStage = function() return 1 end, GetStageType = function() return 0 end,
        GetStartingRoomIndex = function() return 84 end,
        GetCurrentRoomDesc = function() return fixtureRooms[1] end,
        GetRoomByIdx = function(_, index, dimension)
            for _, room in ipairs(fixtureRooms) do if room.SafeGridIndex == index and dimension == 0 then return room end end
            return {Data=nil}
        end,
        GetRooms = function() return { Size = #fixtureRooms, Get = function(_, i) return fixtureRooms[i+1] end } end,
    } end,
    GetRoom = function() return { GetFrameCount = function() return context.roomFrame end,
        GetSpawnSeed = function() return 111 end, GetDecorationSeed = function() return 444 end } end,
    GetNumPlayers = function() return 1 end,
} end
MagicConch = {
    Config = { language = "EN", forcedReply = "None", chances = { positive = 40, neutral = 20, negative = 40 } },
    GetCurrentRoomUsage = function() return context.usageCount end,
    AddCallback = function(_, event, fn) callbacks[event] = fn end,
    RemoveCallback = function(_, event, fn) if callbacks[event] == fn then callbacks[event] = nil end end,
}
-- Deterministic stand-in ONLY: not an implementation of Isaac's RNG API internals.
RNG = function()
    local seed = 1
    return {
        SetSeed = function(_, value, shift)
            assert(value >= 1 and value <= 4294967295 and shift == 35)
            seed = value
        end,
        RandomInt = function(_, max)
            assert(max >= 1 and max % 1 == 0)
            seed = (seed ~ (seed << 13)) & 0xffffffff
            seed = (seed ~ (seed >> 17)) & 0xffffffff
            seed = (seed ~ (seed << 5)) & 0xffffffff
            return seed % max
        end,
    }
end
''')

for path in ROOT.glob("*.lua"):
    lua.execute("assert(load(...))", path.read_text(encoding="utf-8"))
lua.globals().randomModule = lua.execute((ROOT / "magic_conch_random.lua").read_text(encoding="utf-8"))
lua.execute('''include = function(name)
    if name == "magic_conch_random" then return randomModule end
    if name == "magic_conch_rng_rooms" then return roomTests end
    error("Unexpected include: " .. name)
end''')
lua.globals().lang = lua.execute((ROOT / "magic_conch_lang.lua").read_text(encoding="utf-8"))
lua.globals().roomTests = lua.execute((ROOT / "magic_conch_rng_rooms.lua").read_text(encoding="utf-8"))
lua.globals().diagnostics = lua.execute((ROOT / "magic_conch_rng_test.lua").read_text(encoding="utf-8"))

# Keep the reference fixed after new implementations are committed to HEAD.
original = (ROOT / "tests/fixtures/legacy_selector.lua").read_text(encoding="utf-8")
lua.globals().original = lua.execute(original)
lua.execute(r'''
local configs = {
    { language = "EN", chances = {positive=40, neutral=20, negative=40} },
    { language = "KR", chances = {positive=7, neutral=3, negative=7} },
    { language = "Auto", forcedReply = "Positive", chances = {positive=40, neutral=20, negative=40} },
    { language = "EN", forcedReply = "Neutral", chances = {positive=40, neutral=20, negative=40} },
    { language = "KR", forcedReply = "Negative", chances = {positive=40, neutral=20, negative=40} },
    { language = "EN", chances = {positive=0, neutral=0, negative=0} },
}
for _, config in ipairs(configs) do
    for _, seed in ipairs({1, 123456789, 2147483647, 4294967295}) do
        context.startSeed = seed
        for _, room in ipairs({-3, 0, 84, 168}) do
            context.roomIndex = room
            for usage = 0, 199 do
                context.usageCount = usage
                local before, after = original.getRandomString(config), lang.sampleLegacy(config, context)
                assert(before.type == after.type and before.text == after.text, "legacy behavior changed")
            end
        end
    end
end
context.startSeed, context.roomIndex, context.usageCount = 123456789, 84, 4
api = diagnostics.Install(MagicConch, lang)
assert(api.Command(nil, "unrelated", "test") == nil and not api.IsRunning())
for _, args in ipairs({"test 0", "test 100 0", "test 100 1 0", "test 100 1 4294967296",
    "test 1.5", "test nan", "test 100000 20", "test 100 1 1 extra", "predict 51",
    "test rooms 0", "test rooms 5001", "test rooms 100 0", "test rooms 100 1 extra"}) do
    assert(api.Command(nil, "mc", args) == nil and not api.IsRunning(), args)
end
api.Command(nil, "mc", "predict 5")
assert(logs[#logs]:find("prediction=MATCH", 1, true))
assert(context.usageCount == 4)
assert(api.Command(nil, "mc", "test") == nil)
local resumes = 0
while api.IsRunning() do api.Step(); resumes = resumes + 1; assert(resumes < 10000) end
report = api.lastReport
assert(report.completed and not report.error)
assert(report.draws == 1650000 and #report.rows == 165 and report.skipped == 0)
assert(report.predictionErrors == 0)
assert(report.rooms.completed and report.rooms.runs == 1000 and report.rooms.timingMismatches == 0)
assert(report.rooms.draws == 3084036)
primaryLogs = table.concat(logs, "\n")
local legacyRooms = report.rooms.methods.legacy
assert(legacyRooms.byUse[0].n == 169000 and legacyRooms.byUse[1].n == 169000)
assert(legacyRooms.byRoom[84].n == 1000)
assert(legacyRooms.byRow[6].n == 13000 and legacyRooms.byColumn[6].n == 13000)
assert(legacyRooms.transitions.horizontal.positive.counts.negative == 0)
assert(legacyRooms.transitions.second_use.positive.counts.negative == 0)
for _, relation in ipairs({"changed_stage", "changed_stageType", "changed_dimension", "right_first_vs_left_second"}) do
    local p = legacyRooms.pairs[relation]
    assert(p.n == p.textMatches)
end
assert(report.rooms.methods.rng_sum.pairs.changed_stage.n == report.rooms.methods.rng_sum.pairs.changed_stage.textMatches)
assert(report.rooms.methods.keyed.pairs.changed_stage.textMatches < report.rooms.methods.keyed.pairs.changed_stage.n)
assert(report.rooms.actualFloor.legacy.n == 3 and report.rooms.actualFloor.rng_spawn.n == 3)
assert(context.startSeed == 123456789 and context.roomIndex == 84 and context.usageCount == 4)
assert(MagicConch.Config.forcedReply == "None" and MagicConch.Config.chances.positive == 40)
for _, row in ipairs(report.rows) do
    if row.method == "legacy" and row.case == "default_40_20_40" then
        assert(row.counts.positive == 4000 and row.counts.neutral == 2000 and row.counts.negative == 4000)
        assert(row.same100 == 9900 and row.same200text == 9800)
    end
    if row.method == "legacy" and row.case == "total17_7_3_7" then
        assert(row.counts.negative == row.n and row.counts.positive == 0 and row.counts.neutral == 0)
    end
    local forced = row.case:match("^forced_(.+)") or row.case:match("^(.+)_only$")
    if forced then assert(row.counts[forced] == row.n) end
end
-- Optional live observation is off by default and segmented when settings change.
api.Observe(lang.getRandomString(MagicConch.Config), "hotkey")
api.Command(nil, "mc", "watch")
context.usageCount = 0
api.Observe(lang.getRandomString(MagicConch.Config), "hotkey")
context.roomFrame = 300
api.Observe(lang.getRandomString(MagicConch.Config), "API: fixture")
api.Observe(lang.resolveResponse(MagicConch.Config, context, {type="negative",text="Forced fixture"}), "API: forced fixture")
MagicConch.Config.forcedReply = "Positive"
api.Observe(lang.getRandomString(MagicConch.Config), "hotkey")
api.Command(nil, "mc", "stats")
local forcedExcluded = false
for _, message in ipairs(logs) do
    if message:find("WATCH samples=3 enabled=true excludedForced=1", 1, true) then forcedExcluded = true end
end
assert(forcedExcluded, "per-call forced responses contaminated RNG samples")
api.Command(nil, "mc", "watch off")
local countAfterStop = #logs
api.Observe(lang.getRandomString(MagicConch.Config), "hotkey")
assert(#logs == countAfterStop)
context.usageCount, context.roomFrame, MagicConch.Config.forcedReply = 4, 1, "None"
api.Command(nil, "mc", "test rooms 10 1")
while api.IsRunning() do api.Step() end
assert(api.lastReport.completed and api.lastReport.rooms.runs == 10)
-- Cancellation, invalid weights, and replacing the installation stay bounded.
api.Command(nil, "mc", "test 10000 1 1")
assert(api.IsRunning())
api.Command(nil, "mc", "stop")
assert(not api.IsRunning() and not api.lastReport.completed)
MagicConch.Config.chances = {positive=0, neutral=0, negative=0}
api.Command(nil, "mc", "test 100 1 1")
while api.IsRunning() do api.Step() end
assert(api.lastReport.completed and api.lastReport.skipped == 1)
local oldApi = api
api = diagnostics.Install(MagicConch, lang)
assert(not oldApi.IsRunning() and callbacks[ModCallbacks.MC_EXECUTE_CMD] == api.Command)
api.Uninstall()
assert(next(callbacks) == nil)
''')
def plain(value):
    if hasattr(value, "items"):
        return {str(k): plain(v) for k, v in value.items()}
    return value


with tempfile.TemporaryDirectory() as directory:
    fixture = Path(directory) / "test-shim-output.log"
    fixture.write_text(lua.globals().primaryLogs, encoding="utf-8")
    primary, _ = parse_log(fixture)
    keyed_rows = [row for row in primary["rows"] if row["method"] == "keyed"]
    # Fixed regression screens, not a proof of randomness or adjusted significance tests.
    assert all(float(row["typeMaxZ"]) < 6 and float(row["textMaxZ"]) < 6 for row in keyed_rows)
    keyed_pairs = [row for row in primary["pairs"] if row["method"] == "keyed"]
    for pair in keyed_pairs:
        n = int(pair["n"])
        for metric, p in (("typeMatches", .36), ("textMatches", .05)):
            assert abs(int(pair[metric]) - n * p) / math.sqrt(n * p * (1-p)) < 6, pair
    sequence = [plain(row) for row in lua.globals().report.rows.values() if row.method == "keyed"]
    assert all(row["typeZ"] < 6 and row["textZ"] < 6 for row in sequence)
    for row in sequence:
        if row["case"] == "default_40_20_40":
            for metric, lag, p in (("same100", 100, .36), ("same200text", 200, .05)):
                n = row["n"] - lag
                assert abs(row[metric] - n * p) / math.sqrt(n * p * (1-p)) < 6
    evidence = {
        "backend": "actual production Lua 5.3 keyed algorithm; no engine RNG used for these rows",
        "seed": 123456789, "sequenceDraws": 550000, "roomDraws": 1028011,
        "scope": "synthetic contexts; three room descriptors are mocked, not native gameplay",
        "threshold": "fixed 6-standard-deviation regression screens; overlapping strata are not independent tests",
        "predictionErrors": 0, "timingMismatches": 0,
        "sequenceContext": {"stage": 1, "stageType": 0, "dimension": 0, "roomIndex": 84,
            "roomListIndex": 0, "spawnSeed": 111, "decorationSeed": 444, "usageCount": 4},
        "sequence": sequence, "roomStrata": keyed_rows, "pairs": keyed_pairs,
    }
    destination = ROOT / "tests/results/keyed-local.json"
    destination.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fixture.write_text("\n".join(lua.globals().logs.values()), encoding="utf-8")
    parsed, _ = parse_log(fixture)
    assert parsed["header"]["runs"] == "10"
    assert all(int(row["n"]) == 1690 for row in parsed["totals"])
    assert len(parsed["pairs"]) == 12
    fixture.write_text(fixture.read_text(encoding="utf-8") +
        "\n[MC ROOM TEST] BEGIN v2 backend=Isaac.RNG runs=10 seed=1\n", encoding="utf-8")
    try:
        parse_log(fixture)
        raise AssertionError("Incomplete latest block accepted")
    except ValueError as error:
        assert "incomplete" in str(error)
print("PASS: Lua 5.3 syntax; 19,200 legacy equivalence checks; 1,650,000 sequence + 3,084,036 room diagnostic draws")
print("PASS: predictions, fixed weights/forced replies, periodicity, bounds, cancellation, config isolation")
print("PASS: room/row/column/use strata, spatial transitions, floor/dimension collisions, timing, actual-floor fixture, optional watch")
print("keyed executes the actual production Lua algorithm. Native Isaac RNG comparisons use a TEST SHIM here.")
