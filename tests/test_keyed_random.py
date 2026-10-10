"""Execute production Lua: integer reference, rejection sampling and replay checks.

Run: python tests/test_keyed_random.py (requires lupa; no game or RNG shim needed).
"""
from pathlib import Path
from lupa.lua53 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]
MASK = (1 << 64) - 1
STEP = 0x9e3779b97f4a7c15
FIELDS = ("startSeed", "stage", "stageType", "dimension", "roomIndex", "roomListIndex",
          "spawnSeed", "decorationSeed", "usageCount")


def mix(x):
    x &= MASK
    x = ((x ^ (x >> 30)) * 0xbf58476d1ce4e5b9) & MASK
    x = ((x ^ (x >> 27)) * 0x94d049bb133111eb) & MASK
    return x ^ (x >> 31)


def key(context):
    value = 0x4d414749434f4e32
    for field in FIELDS:
        value = mix(value ^ mix(context.get(field, 0) + STEP))
    return value


def bounded(value, domain, maximum):
    state, tries = value ^ domain, 0
    limit = (1 << 32) - (1 << 32) % maximum
    while True:
        state = (state + STEP) & MASK
        word = mix(state) >> 32
        tries += 1
        if word < limit:
            return word % maximum, tries


def runtime():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.globals().randomModule = lua.execute((ROOT / "magic_conch_random.lua").read_text(encoding="utf-8"))
    lua.execute('include = function(name) assert(name == "magic_conch_random"); return randomModule end')
    lua.globals().lang = lua.execute((ROOT / "magic_conch_lang.lua").read_text(encoding="utf-8"))
    return lua


lua = runtime()
random = lua.globals().randomModule
config = lua.table_from({"language": "EN", "chances": {"positive": 40, "neutral": 20, "negative": 40}}, recursive=True)
reference_checks, rejection_cases = 0, 0
for seed in (0, 1, 123456789, 2147483647, 4294967295):
    for index in (-13, -1, 0, 84, 168):
        for usage in (0, 1, 2, 99, 100, 200, 1000000):
            context = dict(startSeed=seed, roomIndex=index, usageCount=usage, stage=12,
                           stageType=5, dimension=2, roomListIndex=42, spawnSeed=4294967295,
                           decorationSeed=2147483648)
            expected_key = key(context)
            actual_key = random.Key(lua.table_from(context))
            assert actual_key & MASK == expected_key
            for domain in (random.TYPE_DOMAIN, random.TEXT_DOMAIN):
                for maximum in (1, 3, 8, 17, 100, 3000000, 2147483649, 4294967296):
                    expected, tries = bounded(expected_key, domain, maximum)
                    assert random.Bounded(actual_key, domain, maximum) == expected
                    reference_checks += 1
                    rejection_cases += tries > 1
assert rejection_cases > 0, "The rejection branch must actually execute"

# Fresh VM loads with different hash traversal order must still choose the same IDs.
# Interleaved rooms / changed language / unrelated calls cannot alter a saved key.
replay_script = r'''
local sequence = {}
local config = {language="EN", chances={positive=40, neutral=20, negative=40}}
for seed=1,20 do
    for room=-3,168 do
        local ctx = {startSeed=seed*1234567, stage=3, stageType=1, dimension=0, roomIndex=room,
            roomListIndex=room+3, spawnSeed=seed*9876543, decorationSeed=123456, usageCount=room%7}
        local first = lang.sample(config, ctx)
        ctx.roomIndex, ctx.roomFrame = room+1, 1800
        lang.sample(config, ctx)
        ctx.roomIndex = room
        local replay = lang.sample(config, ctx)
        assert(first.id == replay.id and first.type == replay.type and first.text == replay.text)
        config.language = "KR"
        assert(lang.sample(config, ctx).id == first.id, "language changed the answer ID")
        config.language = "EN"
        first.id = "mutated" -- A caller cannot corrupt the cached response pool.
        assert(lang.sample(config, ctx).id == replay.id)
        sequence[#sequence+1] = replay.id
    end
end
return table.concat(sequence, ",")
'''
expected_replay = lua.execute(replay_script)
for _ in range(3):
    assert runtime().execute(replay_script) == expected_replay

lua.execute(r'''
local defaults = {language="EN", chances={positive=40,neutral=20,negative=40}}
for _, invalid in ipairs({false, {}, {positive=0,neutral=0,negative=0}, {positive=-1,neutral=2,negative=3},
    {positive=1.5,neutral=2,negative=3}, {positive=0/0,neutral=2,negative=3}}) do
    for usage=0,100 do
        local ctx = {startSeed=1, roomIndex=84, usageCount=usage}
        assert(lang.sample({language="EN",chances=invalid},ctx).id == lang.sample(defaults,ctx).id)
    end
end
local ctx = {startSeed=1, stage=1, stageType=0, dimension=0, roomIndex=84, roomListIndex=3,
    spawnSeed=4, decorationSeed=5, usageCount=0}
local roomKey, drawKey = randomModule.RoomKey(ctx), randomModule.Key(ctx)
for field, value in pairs(ctx) do
    ctx[field] = value+1
    assert(randomModule.Key(ctx) ~= drawKey, "field missing from draw key: "..field)
    assert((randomModule.RoomKey(ctx) == roomKey) == (field == "usageCount"), "wrong room key fields")
    ctx[field] = value
end
for _, bound in ipairs({0,-1,1.5,4294967297}) do
    assert(not pcall(randomModule.Bounded, 1, 1, bound))
end
''')
print(f"PASS: {reference_checks} independent unsigned-integer reference comparisons; {rejection_cases} rejected-word cases")
print("PASS: 3,440 contexts replay identically across four Lua VMs; language/order/timing/caller mutation isolation")
print("PASS: room identity fields, counter identity, invalid bounds and default weight fallback")
