---@class MagicConchLang
---@field LANGUAGE_MAP table
---@field getLanguageTable fun(config: table): table
---@field getRandomString fun(config: table): table
local Random = include("magic_conch_random")

---@type MagicConchLang
local LANGUAGE_MAP = {
    { code = "EN", options = "en", name = "English", font = "gfx/font/Kkubulim.fnt" },
    { code = "KR", options = "kr", name = "Korean", font = "gfx/font/Kkubulim.fnt" },
    -- Add more languages here
    -- Font Feature will be added later
}

-- Translation strings for Magic Conch mod
-- @param language string Language code (e.g. "EN" or "KR")
-- @return table MagicConchStrings table (e.g. { text = "Maybe someday.", type = "neutral" })
local MagicConchStrings = {
    EN = { -- English Translations (8:8:4 ratio, 20 total)
    -- Positive responses (8 total)
    Yes = {text = "Yes.", type = "positive"},
    Absolutely = {text = "Absolutely.", type = "positive"},
    Definitely = {text = "Definitely.", type = "positive"},
    OfCourse = {text = "Of course.", type = "positive"},
    FollowTheConch = {text = "Follow the conch.", type = "positive"},
    ConchKnowsAll = {text = "The conch knows everything.", type = "positive"},
    YouMay = {text = "You may.", type = "positive"},
    Proceed = {text = "Proceed.", type = "positive"},

    -- Negative responses (8 total)
    Nothing = {text = "Do nothing.", type = "negative"},
    Neither = {text = "Neither.", type = "negative"},
    IDontThinkSo = {text = "I don't think so.", type = "negative"},
    No = {text = "No.", type = "negative"},
    DontEvenAsk = {text = "Don't even ask.", type = "negative"},
    NotToday = {text = "Not today.", type = "negative"},
    Forbidden = {text = "Forbidden.", type = "negative"},
    Impossible = {text = "Impossible.", type = "negative"},

    -- Neutral responses (4 total)
    AskAgainLater = {text = "Ask again later.", type = "neutral"},
    UncertainTimes = {text = "Uncertain times.", type = "neutral"},
    MaybeSomeday = {text = "Maybe someday.", type = "neutral"},
    TryAgain = {text = "Try again.", type = "neutral"},
    },
    KR = { -- Korean Translations (8:8:4 ratio for 20 total)
    -- Positive responses (8 total)
    Yes = {text = "좋아.", type = "positive"},
    Absolutely = {text = "물론.", type = "positive"},
    Definitely = {text = "확실해.", type = "positive"},
    OfCourse = {text = "당연하지.", type = "positive"},
    FollowTheConch = {text = "소라고동을 따라.", type = "positive"},
    ConchKnowsAll = {text = "소라고동은 모든 걸 알아.", type = "positive"},
    YouMay = {text = "해도 돼.", type = "positive"},
    Proceed = {text = "진행해.", type = "positive"},
    
    -- Negative responses (8 total)
    Nothing = {text = "가만있어.", type = "negative"},
    Neither = {text = "다 안 돼.", type = "negative"},
    IDontThinkSo = {text = "그것도 안 돼.", type = "negative"},
    No = {text = "안 돼.", type = "negative"},
    DontEvenAsk = {text = "묻지도 마.", type = "negative"},
    NotToday = {text = "오늘은 절대 안 돼.", type = "negative"},
    Forbidden = {text = "금지야.", type = "negative"},
    Impossible = {text = "불가능해.", type = "negative"},
    
    -- Neutral responses (4 total)
    AskAgainLater = {text = "나중에 다시 물어봐.", type = "neutral"},
    UncertainTimes = {text = "불분명한 시기야.", type = "neutral"},
    MaybeSomeday = {text = "언젠가는 하겠지.", type = "neutral"},
    TryAgain = {text = "다시 한 번 물어봐.", type = "neutral"},
    },
    -- Add more translations here
}

-- Get Language Table from Config and Options
-- @param config table Config table (e.g. MagicConch.Config)
-- @return table Language table (e.g. { code = "EN", options = "en", name = "English" })
local function getLanguageTable(config)
    local result = LANGUAGE_MAP[1] -- Default: first language (EN)
    
    -- If config.language is not "Auto", use it directly
    if config and config.language and config.language ~= "Auto" then
        for _, lang in ipairs(LANGUAGE_MAP) do
            if lang.code == config.language then
                result = lang
                break
            end
        end
    -- If config.language is "Auto" or not set, use Options.Language
    elseif Options and Options.Language then
        for _, lang in ipairs(LANGUAGE_MAP) do
            if Options.Language == lang.options then
                result = lang
                break
            end
        end
    end
    
    return result
end

-- Random string from the language table
-- @param config table Config table (e.g. MagicConch.Config)
-- @return table { text = "...", type = "..." }
-- Frozen old selector for comparison only; never used by normal gameplay.
local function sampleLegacy(config, context, rng)
    local langTable = getLanguageTable(config)
    local strings = MagicConchStrings[langTable.code]

    local desiredTypeLower = nil
    if config and type(config.forcedReply) == "string" then
        local v = string.lower(config.forcedReply)
        if v == "positive" or v == "neutral" or v == "negative" then
            desiredTypeLower = v
        end
    end

    -- Deterministic selection based on game seed, room number, and usage count
    local roomIndex = context.roomIndex
    local startSeed = context.startSeed
    local usageCount = context.usageCount
    
    -- Simple hash base
    local rngVal = startSeed + roomIndex + usageCount

    -- 1. Determine Type (if not forced)
    if not desiredTypeLower then
        -- Default chances if missing
        local chances = (config and config.chances) or { positive = 40, neutral = 20, negative = 40 }
        local pos = chances.positive
        local neu = chances.neutral
        local neg = chances.negative
        local total = pos + neu + neg
        
        if total <= 0 then total = 1 end -- prevent div by zero

        -- Generate random value 0..total-1
        -- Use a slightly different hash multiplier to separate type selection from string selection
        local typeRng = rng and rng:RandomInt(total) or (rngVal * 17 + 11) % total
        
        if typeRng < pos then
            desiredTypeLower = "positive"
        elseif typeRng < (pos + neu) then
            desiredTypeLower = "neutral"
        else
            desiredTypeLower = "negative"
        end
    end

    -- 2. Filter strings by Type
    local pool = {}
    for _, v in pairs(strings) do
        if type(v) == "table" and string.lower(v.type) == desiredTypeLower then
            table.insert(pool, v)
        end
    end

    if #pool == 0 then
        -- Fallback to all strings if filtering resulted in empty pool
        for _, v in pairs(strings) do
            table.insert(pool, v)
        end
    end

    if #pool == 0 then
        return nil
    end
    
    -- 3. Select String from Pool
    local idx = rng and (rng:RandomInt(#pool) + 1) or ((rngVal % #pool) + 1)
    
    return pool[idx]
end

-- Sort translation IDs once. Lua pairs() order must not affect saved-seed results.
local pools = {}
for code, strings in pairs(MagicConchStrings) do
    local keys, groups = {}, { positive = {}, neutral = {}, negative = {}, all = {} }
    for key in pairs(strings) do keys[#keys + 1] = key end
    table.sort(keys)
    for _, key in ipairs(keys) do
        local response = strings[key]
        local entry = { id = key, type = response.type, text = response.text }
        groups[response.type][#groups[response.type] + 1] = entry
        groups.all[#groups.all + 1] = entry
    end
    pools[code] = groups
end

local function sample(config, context)
    local key = Random.Key(context)
    local kind = config and type(config.forcedReply) == "string" and string.lower(config.forcedReply) or "none"
    if kind ~= "positive" and kind ~= "neutral" and kind ~= "negative" then
        local pos, neu, neg = Random.Weights(config)
        local roll = Random.Bounded(key, Random.TYPE_DOMAIN, pos + neu + neg)
        kind = roll < pos and "positive" or (roll < pos + neu and "neutral" or "negative")
    end
    local groups = pools[getLanguageTable(config).code]
    local pool = #groups[kind] > 0 and groups[kind] or groups.all
    if #pool == 0 then return nil end
    local entry = pool[Random.Bounded(key, Random.TEXT_DOMAIN, #pool) + 1]
    return { id = entry.id, type = entry.type, text = entry.text }
end

local function getRandomContext()
    local context = Random.Capture()
    context.usageCount = (MagicConch and MagicConch.GetCurrentRoomUsage)
        and MagicConch:GetCurrentRoomUsage() or 0
    return context
end

local function getRandomString(config)
    return sample(config, getRandomContext())
end

-- Return counts, not the mutable translation tables, for distribution diagnostics.
local function getResponseCounts(config)
    local counts = { positive = 0, neutral = 0, negative = 0 }
    for _, response in pairs(MagicConchStrings[getLanguageTable(config).code]) do
        local kind = string.lower(response.type)
        counts[kind] = (counts[kind] or 0) + 1
    end
    return counts
end

return {
    LANGUAGE_MAP = LANGUAGE_MAP,
    getLanguageTable = getLanguageTable,
    getRandomString = getRandomString,
    sample = sample,
    sampleLegacy = sampleLegacy,
    getRandomContext = getRandomContext,
    getResponseCounts = getResponseCounts,
}
