-- Stateless, room-and-counter keyed PRNG. No global or game RNG is consumed.
-- SplitMix64 mixer: Sebastiano Vigna, public domain (2015).
-- https://prng.di.unimi.it/splitmix64.c
-- Lua 5.3 integer arithmetic intentionally wraps modulo 2^64.
local Random = { VERSION = 2, TYPE_DOMAIN = 0x54595045, TEXT_DOMAIN = 0x54455854 }
local STEP = 0x9e3779b97f4a7c15
local FIELDS = { "startSeed", "stage", "stageType", "dimension", "roomIndex", "roomListIndex",
    "spawnSeed", "decorationSeed", "usageCount" }

local function integer(value) return math.tointeger(value) or 0 end

local function mix(value)
    value = (value ~ (value >> 30)) * 0xbf58476d1ce4e5b9
    value = (value ~ (value >> 27)) * 0x94d049bb133111eb
    return value ~ (value >> 31)
end

function Random.Key(context)
    -- Fold each field in order: room+1/use=0 cannot alias room/use=1 by addition.
    local key = 0x4d414749434f4e32 -- domain/version: MAGICON2
    for _, field in ipairs(FIELDS) do
        key = mix(key ~ mix(integer(context[field]) + STEP))
    end
    return key
end

function Random.Bounded(key, domain, maximum)
    assert(math.tointeger(maximum) and maximum >= 1 and maximum <= 0x100000000, "invalid random bound")
    -- Rejection removes the modulo bias for totals not dividing 2^32.
    local limit = 0x100000000 - (0x100000000 % maximum)
    local state = key ~ domain
    while true do
        state = state + STEP
        local word = (mix(state) >> 32) & 0xffffffff
        if word < limit then return word % maximum end
    end
end

function Random.Weights(config)
    local weights = config and config.chances
    if type(weights) ~= "table" then weights = nil end
    local pos, neu, neg = weights and weights.positive, weights and weights.neutral, weights and weights.negative
    local function valid(n) return type(n) == "number" and math.tointeger(n) and n >= 0 and n <= 1000000 end
    if not (valid(pos) and valid(neu) and valid(neg)) or pos + neu + neg == 0 then
        return 40, 20, 40 -- Invalid saved/external settings fall back to the documented default.
    end
    return math.tointeger(pos), math.tointeger(neu), math.tointeger(neg)
end

function Random.Capture(descriptor)
    local game = Game()
    local level, room = game:GetLevel(), game:GetRoom()
    local desc = descriptor or level:GetCurrentRoomDesc()
    -- Use one canonical index for multi-tile rooms and descriptor snapshots.
    local index = desc.SafeGridIndex
    local dimension = -1
    for candidateDimension = 0, 2 do
        local candidate = level:GetRoomByIdx(index, candidateDimension)
        if candidate.Data and candidate.ListIndex == desc.ListIndex then dimension = candidateDimension; break end
    end
    return { startSeed = game:GetSeeds():GetStartSeed(), stage = level:GetStage(), stageType = level:GetStageType(),
        dimension = dimension, roomIndex = index, roomListIndex = desc.ListIndex,
        spawnSeed = descriptor and desc.SpawnSeed or room:GetSpawnSeed(),
        decorationSeed = descriptor and desc.DecorationSeed or room:GetDecorationSeed(), usageCount = 0,
        legacyRoomIndex = descriptor and index or level:GetCurrentRoomIndex() }
end

function Random.RoomKey(context)
    -- ListIndex distinguishes descriptor identities, including separate dimensions.
    -- Exclude usageCount: this identifies the room that owns the counter.
    local parts = { "v2" }
    for i = 1, #FIELDS - 1 do parts[#parts + 1] = tostring(integer(context[FIELDS[i]])) end
    return table.concat(parts, "_")
end

function Random.LegacyRoomKey(context)
    return table.concat({ context.stage, context.stageType, context.legacyRoomIndex or context.roomIndex,
        context.decorationSeed, context.spawnSeed }, "_")
end

return Random
