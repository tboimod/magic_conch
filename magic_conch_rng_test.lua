-- Opt-in diagnostics: mc test [samples per round] [rounds] [seed].
-- Only private RNG objects and synthetic contexts are used. No conch is activated.
-- API reference: https://wofsauge.github.io/IsaacDocs/rep/RNG.html
local Diagnostics = {}
local RoomTests = include("magic_conch_rng_rooms")
local TYPES = { "positive", "neutral", "negative" }
local SHIFT_INDEX = 35
local UINT32_MAX = 4294967295
local CHUNK_SIZE = 2000
local PREFIX = "[MC RNG TEST] "

local function log(message)
    Isaac.DebugString(PREFIX .. message)
    Isaac.ConsoleOutput(PREFIX .. message .. "\n")
end

local function positiveSeed(seed)
    seed = seed % (UINT32_MAX + 1)
    return seed == 0 and 1 or seed
end

local function newRNG(seed)
    local rng = RNG()
    rng:SetSeed(positiveSeed(seed), SHIFT_INDEX)
    return rng
end

local function copyConfig(config)
    local weights = config.chances or { positive = 40, neutral = 20, negative = 40 }
    return {
        language = config.language,
        forcedReply = config.forcedReply,
        chances = { positive = weights.positive, neutral = weights.neutral, negative = weights.negative },
    }
end

local function probabilities(config)
    local forced = string.lower(tostring(config.forcedReply))
    local result, total = {}, 0
    for _, kind in ipairs(TYPES) do
        local weight = config.chances[kind]
        if type(weight) ~= "number" or weight ~= weight or weight < 0
            or weight > 1000000 or weight % 1 ~= 0 then
            return nil, "weights must be nonnegative integers <= 1000000"
        end
        total = total + weight
    end
    -- The game's RandomInt requires a positive integer upper bound.
    if total == 0 then return nil, "all weights are zero; no probability distribution exists" end
    local isForced = forced == "positive" or forced == "neutral" or forced == "negative"
    for _, kind in ipairs(TYPES) do
        result[kind] = isForced and (kind == forced and 1 or 0) or config.chances[kind] / total
    end
    return result
end

local function zScore(observed, n, p)
    if n == 0 then return 0 end
    if p == 0 or p == 1 then return observed == n * p and 0 or math.huge end
    return math.abs(observed - n * p) / math.sqrt(n * p * (1 - p))
end

local function stats()
    return { n = 0, counts = { positive = 0, neutral = 0, negative = 0 },
        texts = { positive = {}, neutral = {}, negative = {} }, history = {},
        same1 = 0, same100 = 0, same200text = 0, predictionErrors = 0 }
end

local function add(result, response)
    assert(response and result.counts[response.type], "invalid response from sampler")
    local n = result.n + 1
    local history = result.history
    local function prior(lag) return history[(n - lag - 1) % 200 + 1] end
    if n > 1 and prior(1).type == response.type then result.same1 = result.same1 + 1 end
    if n > 100 and prior(100).type == response.type then result.same100 = result.same100 + 1 end
    if n > 200 and prior(200).text == response.text and prior(200).type == response.type then
        result.same200text = result.same200text + 1
    end
    history[(n - 1) % 200 + 1] = response
    result.n = n
    result.counts[response.type] = result.counts[response.type] + 1
    local texts = result.texts[response.type]
    texts[response.text] = (texts[response.text] or 0) + 1
end

local function summarize(label, result, expected, poolCounts)
    local maxTypeZ, maxTextZ, iidSame, iidTextSame = 0, 0, 0, 0
    local percentages = {}
    for _, kind in ipairs(TYPES) do
        local count, p, size = result.counts[kind], expected[kind], poolCounts[kind]
        maxTypeZ = math.max(maxTypeZ, zScore(count, result.n, p))
        percentages[#percentages + 1] = string.format("%s=%.3f%%", kind, 100 * count / result.n)
        iidSame = iidSame + p * p
        iidTextSame = iidTextSame + p * p / size
        local seen = 0
        for _, frequency in pairs(result.texts[kind]) do
            seen = seen + 1
            maxTextZ = math.max(maxTextZ, zScore(frequency, count, 1 / size))
        end
        if seen < size then maxTextZ = math.max(maxTextZ, zScore(0, count, 1 / size)) end
    end
    local function rate(count, lag)
        return result.n > lag and string.format("%.3f%%", 100 * count / (result.n - lag)) or "n/a"
    end
    log(string.format("%s n=%d %s typeMaxZ=%.2f textMaxZ=%.2f frequency=%s predictionErrors=%d",
        label, result.n, table.concat(percentages, " "), maxTypeZ, maxTextZ,
        math.max(maxTypeZ, maxTextZ) <= 5 and "OK" or "SUSPECT", result.predictionErrors))
    log(string.format("%s sameType@1=%s sameType@100=%s iidType=%.3f%% sameText@200=%s iidText=%.3f%%",
        label, rate(result.same1, 1), rate(result.same100, 100), 100 * iidSame,
        rate(result.same200text, 200), 100 * iidTextSame))
    return { typeZ = maxTypeZ, textZ = maxTextZ, predictionErrors = result.predictionErrors }
end

local function casesFor(config)
    local cases = { { name = "current", config = copyConfig(config) } }
    local function addCase(name, pos, neu, neg, forced)
        cases[#cases + 1] = { name = name, config = {
            language = config.language, forcedReply = forced or "None",
            chances = { positive = pos, neutral = neu, negative = neg },
        } }
    end
    addCase("default_40_20_40", 40, 20, 40)
    addCase("equal_1_1_1", 1, 1, 1)
    addCase("total17_7_3_7", 7, 3, 7)
    addCase("rare_1_1_98", 1, 1, 98)
    addCase("positive_only", 100, 0, 0)
    addCase("neutral_only", 0, 100, 0)
    addCase("negative_only", 0, 0, 100)
    for _, kind in ipairs(TYPES) do addCase("forced_" .. kind, 40, 20, 40, kind) end
    return cases
end

local function copyContext(context)
    local copy = {}
    for key, value in pairs(context) do copy[key] = value end
    return copy
end

local function selectFor(method, lang, config, context, rng)
    return method == "keyed" and lang.sample(config, context) or lang.sampleLegacy(config, context, rng)
end

local function preview(lang, config, context, count)
    local expected, reason = probabilities(config)
    if not expected then log("PREVIEW skipped: " .. reason); return end
    log(string.format("PREVIEW startSeed=%d room=%d usage=%d language=%s forced=%s",
        context.startSeed, context.roomIndex, context.usageCount,
        lang.getLanguageTable(config).code, tostring(config.forcedReply)))
    log(string.format("CONTEXT selectorVersion=2 stage=%d stageType=%d dimension=%d list=%d spawnSeed=%d decorationSeed=%d",
        context.stage, context.stageType, context.dimension, context.roomListIndex,
        context.spawnSeed, context.decorationSeed))
    log("keyed preview is the LIVE selector from the current room/usage; preview does not consume a use.")
    for i = 1, count do
        local sampleContext = copyContext(context)
        sampleContext.usageCount = context.usageCount + i - 1
        local legacy = lang.sampleLegacy(config, sampleContext)
        local candidate = lang.sample(config, sampleContext)
        log(string.format("PREVIEW #%d keyed=%s:%s id=%s legacy=%s:%s", i,
            candidate.type, candidate.text, candidate.id, legacy.type, legacy.text))
    end
    local actual = lang.getRandomString(config)
    local predicted = lang.sample(config, context)
    log("LIVE_SELECTOR prediction=" .. ((actual.type == predicted.type and actual.text == predicted.text)
        and "MATCH" or "MISMATCH") .. " (read-only; no use consumed)")
end

local function runSuite(lang, config, context, samples, rounds, seed, report)
    log(string.format("BEGIN v2 backend=SplitMix64+Isaac.RNG samples=%d rounds=%d seed=%d room=%d usage=%d shift=%d",
        samples, rounds, seed, context.roomIndex, context.usageCount, SHIFT_INDEX))
    log("Each round has a different recorded seed; both methods use identical weights and response pools.")
    log("frequency=OK means max |z| <= 5, a diagnostic screen, NOT proof of independence or randomness.")
    log("textMaxZ checks uniform phrases WITHIN each type; @100/@200 expose periodic patterns.")
    log("Predictions use private copies before sampling; same seed/state/call order is predictable for BOTH methods.")
    log("keyed is LIVE: stateless full context/counter, sorted translation IDs, separate type/text draws. Other methods are baselines.")
    preview(lang, config, context, 10)
    for _, case in ipairs(casesFor(config)) do
        local expected, reason = probabilities(case.config)
        if not expected then
            log("SKIP case=" .. case.name .. " reason=" .. reason)
            report.skipped = report.skipped + 1
        else
            local poolCounts = lang.getResponseCounts(case.config)
            for _, kind in ipairs(TYPES) do assert(poolCounts[kind] > 0, "empty response pool: " .. kind) end
            log(string.format("CASE %s expected=%.3f/%.3f/%.3f%% (positive/neutral/negative)", case.name,
                expected.positive * 100, expected.neutral * 100, expected.negative * 100))
            for round = 1, rounds do
                local roundSeed = ((seed - 1 + (round - 1) * 2654435761) % UINT32_MAX) + 1
                for _, method in ipairs({ "legacy", "rng", "keyed" }) do
                    local rng = method == "rng" and newRNG(roundSeed + context.roomIndex) or nil
                    local predictionRNG = method == "rng" and newRNG(roundSeed + context.roomIndex) or nil
                    local sampleContext = copyContext(context)
                    sampleContext.startSeed = roundSeed
                    -- Save predictions BEFORE drawing from the stream under test.
                    local predictions = {}
                    for i = 1, math.min(samples, 100) do
                        sampleContext.usageCount = context.usageCount + i - 1
                        predictions[i] = selectFor(method, lang, case.config, sampleContext, predictionRNG)
                    end
                    local result = stats()
                    for i = 1, samples do
                        sampleContext.usageCount = context.usageCount + i - 1
                        local response = selectFor(method, lang, case.config, sampleContext, rng)
                        if predictions[i] and (response.type ~= predictions[i].type or response.text ~= predictions[i].text) then
                            result.predictionErrors = result.predictionErrors + 1
                        end
                        add(result, response)
                        if i % CHUNK_SIZE == 0 then coroutine.yield() end
                    end
                    local label = string.format("case=%s round=%d seed=%d method=%s", case.name, round, roundSeed, method)
                    local summary = summarize(label, result, expected, poolCounts)
                    report.rows[#report.rows + 1] = { case = case.name, round = round, seed = roundSeed,
                        method = method, counts = result.counts, n = result.n,
                        typeZ = summary.typeZ, textZ = summary.textZ, predictionErrors = summary.predictionErrors,
                        same100 = result.same100, same200text = result.same200text }
                    report.draws = report.draws + samples
                    report.predictionErrors = report.predictionErrors + result.predictionErrors
                    if math.max(summary.typeZ, summary.textZ) > 5 then
                        report.suspect[method] = report.suspect[method] + 1
                    end
                end
            end
        end
        coroutine.yield()
    end
    log(string.format("END draws=%d rows=%d skipped=%d predictionErrors=%d suspectLegacy=%d suspectRNG=%d suspectKeyed=%d",
        report.draws, #report.rows, report.skipped, report.predictionErrors, report.suspect.legacy, report.suspect.rng, report.suspect.keyed))
    log("Gameplay selector=keyed. Repeated answers are allowed; no anti-repeat or forced quota is used.")
    report.sequenceCompleted = true
end

local function integerArg(value, default, min, max)
    if value == nil then return default end
    local n = tonumber(value)
    if not n or n ~= n or n % 1 ~= 0 or n < min or n > max then return nil end
    return n
end

function Diagnostics.Install(mod, lang)
    -- Allows a console-only hot install without reloading/resetting gameplay state.
    if mod.RNGDiagnostics then mod.RNGDiagnostics.Uninstall() end
    local job = nil
    local api = { lastReport = nil }
    local watch = { enabled = false, segments = {}, n = 0, excludedForced = 0 }
    function api.Observe(response, source)
        if not watch.enabled then return end
        -- Explicit per-call responses are decisions by another mod, not RNG samples.
        if response.forced then
            watch.excludedForced = watch.excludedForced + 1
            Isaac.DebugString("[MC RNG WATCH] FORCED_EXCLUDED n=" .. watch.excludedForced .. " source=" .. tostring(source))
            return
        end
        local game, config = Game(), copyConfig(mod.Config)
        config.language = lang.getLanguageTable(config).code
        local expected = probabilities(config)
        if not expected then return end
        local c = config.chances
        local key = table.concat({ config.language, tostring(config.forcedReply), c.positive, c.neutral, c.negative }, ":")
        local segment = watch.segments[key]
        if not segment then
            segment = { expected = expected, pools = lang.getResponseCounts(config), total = RoomTests.Histogram(),
                groups = { usage = {}, entryFrame = {}, roomType = {}, stage = {}, source = {}, visit = {} } }
            watch.segments[key] = segment
        end
        local level, room = game:GetLevel(), game:GetRoom()
        local desc, usage = level:GetCurrentRoomDesc(), mod:GetCurrentRoomUsage()
        local frame = room:GetFrameCount()
        local timing = frame <= 1 and "0..1" or (frame <= 30 and "2..30" or (frame <= 300 and "31..300" or "301+"))
        local tags = { usage = usage < 3 and tostring(usage) or "3+", entryFrame = timing,
            roomType = tostring(desc.Data.Type), stage = tostring(level:GetStage()),
            source = source == "hotkey" and "hotkey" or "api", visit = desc.VisitedCount <= 1 and "first_visit" or "revisit" }
        for name, tag in pairs(tags) do
            local group = segment.groups[name]
            if not group[tag] then group[tag] = RoomTests.Histogram() end
            RoomTests.Add(group[tag], response)
        end
        RoomTests.Add(segment.total, response)
        watch.n = watch.n + 1
        Isaac.DebugString(string.format("[MC RNG WATCH] DRAW n=%d config=%s seed=%d stage=%d stageType=%d index=%d list=%d spawnSeed=%d visited=%d usage=%d roomFrame=%d source=%q response=%s text=%q",
            watch.n, key, game:GetSeeds():GetStartSeed(), level:GetStage(), level:GetStageType(),
            level:GetCurrentRoomIndex(), desc.ListIndex, desc.SpawnSeed, desc.VisitedCount, usage, frame,
            tostring(source), response.type, response.text))
    end
    local function watchSummary()
        log("WATCH samples=" .. watch.n .. " enabled=" .. tostring(watch.enabled) .. " excludedForced=" .. watch.excludedForced)
        for key, segment in pairs(watch.segments) do
            RoomTests.Describe("OBSERVED config=" .. key, segment.total, segment.expected, segment.pools, true)
            for name, groups in pairs(segment.groups) do
                RoomTests.DescribeGroups("OBSERVED config=" .. key .. " group=" .. name, groups, segment.expected, segment.pools)
            end
        end
        log("Watch is observational: route/timing/config selection can confound these counts. usage is captured BEFORE both hotkey/API increment it.")
    end
    local function contextNow()
        return lang.getRandomContext()
    end
    local function stop()
        if job then log("STOPPED (partial results only)") end
        job = nil
    end
    function api.Step()
        if not job then return end
        local ok, err = coroutine.resume(job)
        if not ok then
            log("ERROR " .. tostring(err))
            api.lastReport.error = tostring(err)
            job = nil
        elseif coroutine.status(job) == "dead" then
            job = nil
        end
    end
    function api.IsRunning() return job ~= nil end
    function api.Command(_, command, parameters)
        if string.lower(command) ~= "mc" then return end
        local args = {}
        for arg in (parameters or ""):gmatch("%S+") do args[#args + 1] = arg end
        local action = string.lower(args[1] or "help")
        if action == "stop" then stop(); return end
        if action == "stats" then watchSummary(); return end
        if action == "watch" then
            if args[2] == "off" then watch.enabled = false; watchSummary()
            elseif args[2] == nil or args[2] == "on" then
                watch = { enabled = true, segments = {}, n = 0, excludedForced = 0 }
                log("WATCH enabled with fresh counters. Draws go to log.txt; mc stats summarizes; mc watch off stops.")
            else log("Usage: mc watch [on|off]") end
            return
        end
        if action ~= "test" and action ~= "predict" then
            log("Usage: mc test [samples=10000] [rounds=5] [seed=current] | mc test rooms [runs=1000] [seed=current] | mc predict [count=10] | mc watch | mc stats | mc stop")
            return
        end
        if job then log("A test is running. Use mc stop before starting another."); return end
        if Game():GetNumPlayers() == 0 then log("Start or continue a run first."); return end
        local context = contextNow()
        local config = copyConfig(mod.Config)
        -- Resolve Auto once so a running test has one fixed language.
        config.language = lang.getLanguageTable(config).code
        if action == "predict" then
            local count = integerArg(args[2], 10, 1, 50)
            if not count or #args > 2 then log("Usage: mc predict [count: 1..50]"); return end
            preview(lang, config, context, count)
            return
        end
        if args[2] == "rooms" then
            local runs = integerArg(args[3], 1000, 10, 5000)
            local seed = integerArg(args[4], positiveSeed(context.startSeed), 1, UINT32_MAX)
            if not runs or not seed or #args > 4 then
                log("Usage: mc test rooms [runs:10..5000] [seed:1..4294967295]"); return
            end
            local report = { completed = false }
            api.lastReport = report
            job = coroutine.create(function()
                report.rooms = RoomTests.Run(lang, config, context, runs, seed, { newRNG = newRNG, probabilities = probabilities })
                report.completed = report.rooms.completed
            end)
            log("Room-entry test queued. Detailed room/phrase/transition strata go to log.txt.")
            api.Step()
            return
        end
        local samples = integerArg(args[2], 10000, 100, 100000)
        local rounds = integerArg(args[3], 5, 1, 20)
        local seed = integerArg(args[4], positiveSeed(context.startSeed), 1, UINT32_MAX)
        if not samples or not rounds or not seed or #args > 4 or samples * rounds > 500000 then
            log("Usage: mc test [samples:100..100000] [rounds:1..20] [seed:1..4294967295]; samples*rounds <= 500000")
            return
        end
        local report = { completed = false, rows = {}, draws = 0, skipped = 0,
            predictionErrors = 0, suspect = { legacy = 0, rng = 0, keyed = 0 } }
        api.lastReport = report
        job = coroutine.create(function()
            runSuite(lang, config, context, samples, rounds, seed, report)
            report.rooms = RoomTests.Run(lang, config, context, 1000, seed, { newRNG = newRNG, probabilities = probabilities })
            report.completed = report.rooms.completed
            log("ALL_DONE sequenceDraws=" .. report.draws .. " roomDraws=" .. report.rooms.draws)
        end)
        log("Queued. Runs in render chunks, including while the console is open. Full output is in log.txt.")
        api.Step()
        -- Always return nil from MC_EXECUTE_CMD (vanilla compatibility).
    end
    function api.Uninstall()
        stop()
        watch.enabled = false
        mod:RemoveCallback(ModCallbacks.MC_EXECUTE_CMD, api.Command)
        mod:RemoveCallback(ModCallbacks.MC_POST_RENDER, api.Step)
        mod:RemoveCallback(ModCallbacks.MC_PRE_GAME_EXIT, stop)
    end
    mod:AddCallback(ModCallbacks.MC_EXECUTE_CMD, api.Command)
    mod:AddCallback(ModCallbacks.MC_POST_RENDER, api.Step)
    mod:AddCallback(ModCallbacks.MC_PRE_GAME_EXIT, stop)
    mod.RNGDiagnostics = api
    return api
end

return Diagnostics
