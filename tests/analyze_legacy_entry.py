"""Exhaustive phase analysis of the actual Lua legacy selector, without Isaac RNG.

The 200 seed residues cover the legacy 40/20/40 type+phrase cycle. They are NOT
a sample of real generated dungeon layouts or the game's distribution of seeds.
"""
import argparse
import json
from pathlib import Path

from lupa.lua53 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--seed", type=int, default=4263037529)
parser.add_argument("--output", type=Path, default=ROOT / "tests/results/legacy-room-entry.json")
args = parser.parse_args()
if not 1 <= args.seed <= 4294967295:
    parser.error("seed must be 1..4294967295")
lua = LuaRuntime(unpack_returned_tuples=True)
lua.globals().randomModule = lua.execute((ROOT / "magic_conch_random.lua").read_text(encoding="utf-8"))
lua.execute('include = function(name) assert(name == "magic_conch_random"); return randomModule end')
lang = lua.execute((ROOT / "magic_conch_lang.lua").read_text(encoding="utf-8"))
lua.globals().lang = lang
data = lua.execute(r'''
local selectedSeed = ...
local config = { language = "EN", forcedReply = "None", chances = { positive=40, neutral=20, negative=40 } }
local function hist() return { positive=0, neutral=0, negative=0 } end
local function add(h, value) h[value.type] = h[value.type] + 1 end
local result = { uses = { [0]=hist(), [1]=hist(), [2]=hist() }, rooms={}, horizontal={}, vertical={},
    currentGrid=hist(), currentGridPattern={}, firstEqualsNeighborSecond=0, neighborPairs=0 }
for _, kind in ipairs({"positive", "neutral", "negative"}) do
    result.horizontal[kind], result.vertical[kind] = hist(), hist()
end
for room=0,168 do result.rooms[room] = hist() end
for seed=1,200 do
    local first, second = {}, {}
    for room=0,168 do
        for usage=0,2 do
            local response = lang.sampleLegacy(config, {startSeed=seed, roomIndex=room, usageCount=usage})
            add(result.uses[usage], response)
            if usage == 0 then first[room] = response; add(result.rooms[room], response)
            elseif usage == 1 then second[room] = response end
        end
        if room % 13 > 0 then
            add(result.horizontal[first[room-1].type], first[room])
            result.neighborPairs = result.neighborPairs + 1
            if second[room-1].type == first[room].type and second[room-1].text == first[room].text then
                result.firstEqualsNeighborSecond = result.firstEqualsNeighborSecond + 1
            end
        end
        if room >= 13 then add(result.vertical[first[room-13].type], first[room]) end
    end
end
local symbols = {positive="P", neutral="U", negative="N"}
for row=0,12 do
    local pattern = {}
    for column=0,12 do
        local response = lang.sampleLegacy(config, {startSeed=selectedSeed, roomIndex=row*13+column, usageCount=0})
        add(result.currentGrid, response)
        pattern[#pattern+1] = symbols[response.type]
    end
    result.currentGridPattern[row] = table.concat(pattern)
end
result.room84 = lang.sampleLegacy(config, {startSeed=selectedSeed, roomIndex=84, usageCount=0}).type
return result
''', args.seed)


def plain(value):
    if hasattr(value, "items"):
        return {str(k): plain(v) for k, v in value.items()}
    return value


report = {
    "backend": "actual legacy Lua selector; no native RNG used",
    "scope": "exhaustive 200 residue phases x 169 synthetic slots x uses 0,1,2",
    "selected_run_seed": args.seed,
    "draws": 101400 + 169 + 1,
    "warning": "Synthetic equal-weight grid. Not actual floor generation or real player routes.",
    "results": plain(data),
}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({key: report["results"][key] for key in
    ("uses", "horizontal", "vertical", "currentGrid", "room84", "neighborPairs", "firstEqualsNeighborSecond")},
    ensure_ascii=False, indent=2))
print(f"Saved: {args.output}")
