-- Room-entry diagnostics. Synthetic grids are NOT generated dungeon layouts.
local Rooms = {}
local Random = include("magic_conch_random")
local TYPES = { "positive", "neutral", "negative" }
local METHODS = { "legacy", "rng_sum", "keyed" }
local MASK = 0xffffffff

local function log(message)
    Isaac.DebugString("[MC ROOM TEST] " .. message)
    -- Detailed strata go to the log; keep the game console usable.
    if message:match("^BEGIN") or message:match("^END") or message:match("^TOTAL") then
        Isaac.ConsoleOutput("[MC ROOM TEST] " .. message .. "\n")
    end
end

function Rooms.Histogram()
    return { n = 0, counts = { positive = 0, neutral = 0, negative = 0 },
        texts = { positive = {}, neutral = {}, negative = {} } }
end

function Rooms.Add(hist, response)
    hist.n = hist.n + 1
    hist.counts[response.type] = hist.counts[response.type] + 1
    local phrases = hist.texts[response.type]
    phrases[response.text] = (phrases[response.text] or 0) + 1
end

local function bucket(groups, key, response)
    if not groups[key] then groups[key] = Rooms.Histogram() end
    Rooms.Add(groups[key], response)
end

local function same(a, b) return a.type == b.type and a.text == b.text end

local function zScore(count, n, p)
    if n == 0 then return 0 end
    if p == 0 or p == 1 then return count == n * p and 0 or math.huge end
    return math.abs(count - n * p) / math.sqrt(n * p * (1 - p))
end

local function describe(label, hist, expected, poolCounts, printPhrases)
    if hist.n == 0 then log(label .. " n=0"); return end
    local typeZ, textZ, topText, topCount, maxDelta = 0, 0, "", 0, 0
    for _, kind in ipairs(TYPES) do
        local count, size = hist.counts[kind], poolCounts[kind]
        typeZ = math.max(typeZ, zScore(count, hist.n, expected[kind]))
        maxDelta = math.max(maxDelta, math.abs(count / hist.n - expected[kind]) * 100)
        local seen = 0
        for text, frequency in pairs(hist.texts[kind]) do
            seen = seen + 1
            textZ = math.max(textZ, zScore(frequency, count, 1 / size))
            if frequency > topCount then topText, topCount = text, frequency end
            if printPhrases then
                log(string.format("PHRASE %s type=%s count=%d withinType=%.3f%% text=%q",
                    label, kind, frequency, frequency / count * 100, text))
            end
        end
        if seen < size then textZ = math.max(textZ, zScore(0, count, 1 / size)) end
    end
    log(string.format("%s n=%d counts=%d/%d/%d pct=%.3f/%.3f/%.3f maxDeltaPP=%.3f typeMaxZ=%.2f textMaxZ=%.2f top=%q topCount=%d",
        label, hist.n, hist.counts.positive, hist.counts.neutral, hist.counts.negative,
        100 * hist.counts.positive / hist.n, 100 * hist.counts.neutral / hist.n,
        100 * hist.counts.negative / hist.n, maxDelta, typeZ, textZ, topText, topCount))
end

local function describeGroups(label, groups, expected, counts)
    local keys = {}
    for key in pairs(groups) do keys[#keys + 1] = key end
    table.sort(keys)
    for _, key in ipairs(keys) do describe(label .. " bucket=" .. key, groups[key], expected, counts) end
end

local function newMethod()
    return { byUse = {}, byRoom = {}, byRow = {}, byColumn = {}, byStage = {}, bySeedResidue = {},
        transitions = { horizontal = {}, vertical = {}, second_use = {} },
        current = Rooms.Histogram(), adjacentSeeds = Rooms.Histogram(), special = Rooms.Histogram(),
        pairs = {}, first = {}, second = {} }
end

local function pair(result, name, a, b)
    local p = result.pairs[name] or { n = 0, typeMatches = 0, textMatches = 0 }
    result.pairs[name] = p
    p.n = p.n + 1
    if a.type == b.type then p.typeMatches = p.typeMatches + 1 end
    if same(a, b) then p.textMatches = p.textMatches + 1 end
end

local function transition(result, name, before, after)
    bucket(result.transitions[name], before.type, after)
end

function Rooms.Capture(context)
    local level = Game():GetLevel()
    local snapshot = { stage = level:GetStage(), stageType = level:GetStageType(), rooms = {},
        startingRoom = level:GetStartingRoomIndex() }
    local descriptors = level:GetRooms()
    -- GetRooms returns descriptors once, including multi-tile rooms. Preserve list IDs.
    for i = 0, descriptors.Size - 1 do
        local desc = descriptors:Get(i)
        if desc.Data then
            local captured = Random.Capture(desc)
            snapshot.rooms[#snapshot.rooms + 1] = { roomIndex = desc.SafeGridIndex,
                gridIndex = desc.GridIndex, listIndex = desc.ListIndex, spawnSeed = desc.SpawnSeed,
                decorationSeed = desc.DecorationSeed, dimension = captured.dimension,
                roomType = desc.Data.Type, visited = desc.VisitedCount }
        end
    end
    return snapshot
end

function Rooms.Run(lang, config, context, runs, seed, shared)
    local expected, reason = shared.probabilities(config)
    local report = { completed = false, runs = runs, draws = 0, methods = {} }
    if not expected then
        log("END skipped=" .. reason); report.skipped = reason; report.completed = true; return report
    end
    local counts = lang.getResponseCounts(config)
    for _, kind in ipairs(TYPES) do assert(counts[kind] > 0, "empty response pool") end
    local ok, snapshot = pcall(Rooms.Capture, context)
    if not ok then snapshot = nil end
    local baseStage, baseStageType = snapshot and snapshot.stage or 1, snapshot and snapshot.stageType or 0
    log(string.format("BEGIN v3 backend=SplitMix64+Isaac.RNG runs=%d seed=%d grid=0..168 uses=0,1,2 stage=%d stageType=%d",
        runs, seed, baseStage, baseStageType))
    log(string.format("EXPECTED pct=%.6f/%.6f/%.6f forced=%s language=%s", expected.positive * 100,
        expected.neutral * 100, expected.negative * 100, tostring(config.forcedReply), config.language))
    log("Synthetic: all 169 slots have equal weight; these are NOT actual floor layouts or player routes.")
    log("keyed is the LIVE stateless room+counter selector. legacy and rng_sum are comparison baselines only.")
    log("Native rng_sum advances through uses 0,1,2. keyed calculates each use independently from the full context.")
    log("Z scores are descriptive IID screens: shared seeds, overlapping strata and deterministic grids are dependent; no multiple-testing certification.")
    log("PHRASE counts are conditional on type. TOTAL contains every first use once; strata overlap and must not be added together.")
    local work = 0
    local function sample(method, ctx, rng)
        report.draws = report.draws + 1
        work = work + 1
        if work % 2000 == 0 then coroutine.yield() end
        return method == "keyed" and lang.sample(config, ctx) or lang.sampleLegacy(config, ctx, rng)
    end
    local function rngFor(method, ctx)
        if method ~= "rng_sum" then return nil end
        return shared.newRNG(ctx.startSeed + ctx.roomIndex)
    end
    for _, method in ipairs(METHODS) do report.methods[method] = newMethod() end
    for run = 1, runs do
        -- Full-width deterministic seed sample independent of the RNG under test.
        local runSeed = ((seed - 1 + (run - 1) * 2654435761) % MASK) + 1
        local ctx = { startSeed = runSeed, roomIndex = 0, usageCount = 0,
            stage = 1 + (baseStage - 1 + run - 1) % 12,
            stageType = (baseStageType + math.floor((run - 1) / 12)) % 6, dimension = 0 }
        for room = 0, 168 do
            ctx.roomIndex = room
            for _, method in ipairs(METHODS) do
                local result, rng = report.methods[method], rngFor(method, ctx)
                for usage = 0, 2 do
                    ctx.usageCount = usage
                    local response = sample(method, ctx, rng)
                    bucket(result.byUse, usage, response)
                    if usage == 0 then
                        result.first[room] = response
                        bucket(result.byRoom, room, response)
                        bucket(result.byRow, math.floor(room / 13), response)
                        bucket(result.byColumn, room % 13, response)
                        bucket(result.byStage, ctx.stage, response)
                        bucket(result.bySeedResidue, runSeed % 10, response)
                        if run == 1 then Rooms.Add(result.current, response) end
                    elseif usage == 1 then
                        result.second[room] = response
                        transition(result, "second_use", result.first[room], response)
                    end
                end
                ctx.usageCount = 0
                local first = result.first[room]
                for _, field in ipairs({ "stage", "stageType", "dimension" }) do
                    local before = ctx[field]
                    ctx[field] = before + 1
                    pair(result, "changed_" .. field, first, sample(method, ctx, rngFor(method, ctx)))
                    ctx[field] = before
                end
                if room % 13 > 0 then
                    transition(result, "horizontal", result.first[room - 1], first)
                    pair(result, "right_first_vs_left_second", result.second[room - 1], first)
                end
                if room >= 13 then transition(result, "vertical", result.first[room - 13], first) end
            end
        end
        if run == 1 then
            local code = { positive = "P", neutral = "U", negative = "N" }
            for _, method in ipairs(METHODS) do
                for row = 0, 12 do
                    local cells = {}
                    for column = 0, 12 do cells[#cells + 1] = code[report.methods[method].first[row * 13 + column].type] end
                    log(string.format("GRID method=%s seed=%d row=%d pattern=%s (P=positive,U=neutral,N=negative)",
                        method, runSeed, row, table.concat(cells)))
                end
            end
        end
        -- A second seed population: adjacent numeric seeds, first draw at the same room.
        ctx.startSeed, ctx.roomIndex = ((seed - 1 + run - 1) % MASK) + 1, context.roomIndex
        ctx.stage, ctx.stageType, ctx.dimension, ctx.usageCount = baseStage, baseStageType, 0, 0
        for _, method in ipairs(METHODS) do
            Rooms.Add(report.methods[method].adjacentSeeds, sample(method, ctx, rngFor(method, ctx)))
            -- Named here as synthetic indices, not assertions that all special rooms exist.
            for _, index in ipairs({ -1, -2, -3, -4, -5, -6, -7, -8, -9, -10, -11, -12, -13 }) do
                ctx.roomIndex = index
                Rooms.Add(report.methods[method].special, sample(method, ctx, rngFor(method, ctx)))
            end
            ctx.roomIndex = context.roomIndex
        end
        if run % 100 == 0 then log("PROGRESS runs=" .. run .. "/" .. runs) end
    end
    for _, method in ipairs(METHODS) do
        local result = report.methods[method]
        describe("TOTAL method=" .. method .. " usage=0", result.byUse[0], expected, counts, true)
        describe("CURRENT_GRID method=" .. method, result.current, expected, counts, true)
        describe("ADJACENT_SEEDS method=" .. method, result.adjacentSeeds, expected, counts)
        describe("SPECIAL_INDICES method=" .. method, result.special, expected, counts)
        for _, name in ipairs({ "byUse", "byRoom", "byRow", "byColumn", "byStage", "bySeedResidue" }) do
            describeGroups("STRATUM method=" .. method .. " group=" .. name, result[name], expected, counts)
        end
        for _, name in ipairs({ "horizontal", "vertical", "second_use" }) do
            describeGroups("CONDITIONAL method=" .. method .. " relation=" .. name .. " given", result.transitions[name], expected, counts)
        end
        for _, name in ipairs({ "changed_stage", "changed_stageType", "changed_dimension", "right_first_vs_left_second" }) do
            local p = result.pairs[name]
            log(string.format("PAIR method=%s relation=%s n=%d typeMatches=%d textMatches=%d typePct=%.3f textPct=%.3f",
                method, name, p.n, p.typeMatches, p.textMatches, p.typeMatches / p.n * 100, p.textMatches / p.n * 100))
        end
    end
    -- Read-only actual floor snapshot; do not generate/warp to rooms to inflate sample size.
    report.actualFloor = {}
    if snapshot then
        log(string.format("FLOOR_SNAPSHOT rooms=%d stage=%d stageType=%d startingRoom=%d usage=0 counterfactual=true",
            #snapshot.rooms, snapshot.stage, snapshot.stageType, snapshot.startingRoom))
        for _, method in ipairs({ "legacy", "rng_sum", "rng_spawn", "keyed" }) do
            local total, byType = Rooms.Histogram(), {}
            for _, room in ipairs(snapshot.rooms) do
                local ctx = { startSeed = context.startSeed, roomIndex = room.roomIndex, usageCount = 0,
                    stage = snapshot.stage, stageType = snapshot.stageType, dimension = room.dimension,
                    roomListIndex = room.listIndex, spawnSeed = room.spawnSeed, decorationSeed = room.decorationSeed }
                local rng = method == "rng_spawn" and shared.newRNG(room.spawnSeed)
                    or (method == "rng_sum" and shared.newRNG(ctx.startSeed + ctx.roomIndex) or nil)
                local response = sample(method, ctx, rng)
                Rooms.Add(total, response)
                bucket(byType, room.roomType, response)
                log(string.format("ACTUAL_ROOM method=%s list=%d index=%d grid=%d roomType=%d visited=%d spawnSeed=%d decorationSeed=%d dimension=%d response=%s text=%q",
                    method, room.listIndex, room.roomIndex, room.gridIndex, room.roomType, room.visited,
                    room.spawnSeed, room.decorationSeed, room.dimension, response.type, response.text))
            end
            describe("ACTUAL_FLOOR method=" .. method, total, expected, counts, true)
            describeGroups("ACTUAL_ROOM_TYPE method=" .. method, byType, expected, counts)
            report.actualFloor[method] = total
        end
        log("Actual snapshot is one floor, including unvisited descriptors; small/type-skewed samples are descriptive only.")
    else
        log("FLOOR_SNAPSHOT unavailable (offline harness or level API error); synthetic results remain separate.")
    end
    -- Frame count is not an input to either selector. Verify varied delays explicitly.
    report.timingMismatches = 0
    for _, method in ipairs(METHODS) do
        local ctx = { startSeed = context.startSeed, roomIndex = context.roomIndex, usageCount = 0,
            stage = baseStage, stageType = baseStageType, dimension = 0 }
        local first = sample(method, ctx, rngFor(method, ctx))
        for _, frame in ipairs({ 0, 1, 10, 30, 60, 300, 1800 }) do
            ctx.roomFrame = frame
            if not same(first, sample(method, ctx, rngFor(method, ctx))) then
                report.timingMismatches = report.timingMismatches + 1
            end
        end
    end
    log("TIMING only selection tested; input availability/spam cooldown can reject activation separately. frameMismatches=" .. report.timingMismatches)
    log(string.format("END runs=%d firstUsesPerMethod=%d draws=%d timingMismatches=%d", runs, runs * 169,
        report.draws, report.timingMismatches))
    report.completed = true
    return report
end

Rooms.Log = log
Rooms.Describe = describe
Rooms.DescribeGroups = describeGroups
return Rooms
