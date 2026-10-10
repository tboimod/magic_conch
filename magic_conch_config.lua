---@class MagicConchConfig
---@field Init fun(mod: table): table
---@field Load fun(mod: table): boolean
---@field Save fun(mod: table)
---@field Reset fun(mod: table)
local MagicConch_Config = {}

local VERSION = "1.0" -- Version of the mod
MagicConch_Config.VERSION = VERSION

-- Default Config
local DefaultConfig = {
    enabled = true,
    deleteMode = false, -- Delete Mode  
    language = "Auto",   -- "Auto", "EN", "KR" (edit in magic_conch_lang.lua)
    forcedReply = "None", -- Forced Reply mode: "None", "Positive", "Neutral", "Negative"
    hotkey = Keyboard.KEY_N,
    displayStyle = 1, -- 0: Fortune Machine Style, 1: Item-like Style
    debugMode = false, -- Debug Mode
    debugHudX = 60,    -- Debug HUD X coordinate (default 60)
    debugHudY = 40,    -- Debug HUD Y coordinate (default 40)
    attemptsPerRoom = 0, -- Number of attempts allowed per room (0 = unlimited)
    
    -- UI Positions
    iconX = 430,       -- Magic Conch icon X position
    iconY = 265,       -- Magic Conch icon Y position
    resultPosition = false, -- false: native HUD; {x,y}: custom result text top-left
    
    -- Probability Weights (Total doesn't need to be 100, but Recommended)
    chances = {
        positive = 40,
        neutral = 20,
        negative = 40
    },

    -- Timing Settings (in frames, 30fps)
    timing = {
        shake = 15,        -- Screen Shake (0.5s)
        wait = 45,         -- Wait Time (1.5s)
        display = 60,     -- Display Time (2s)
        cooldown = 0      -- Cooldown (0s)
    }
}

-- JSON library for saving and loading config
local json = nil
pcall(function() json = require("json") end)
if not json then
    json = {
        encode = function(data) return tostring(data) end,
        decode = function(str) return {} end,
    }
end

-- Initialize the config table
---@param mod table
---@return table
function MagicConch_Config.Init(mod)
    mod.Config = {}
    for k, v in pairs(DefaultConfig) do
        if mod.Config[k] == nil then
            mod.Config[k] = v
        end
    end
    mod.Config.Version = VERSION
    return mod.Config
end

-- Load the config
---@param mod table
---@return boolean
-- Internal: load full saved blob
local function loadAll(mod)
    if not mod:HasData() then return {} end
    local ok, data = pcall(function() return json.decode(Isaac.LoadModData(mod)) end)
    if ok and type(data) == "table" then
        return data
    end
    return {}
end

-- Load the config
---@param mod table
---@return boolean
function MagicConch_Config.Load(mod)
    local data = loadAll(mod)
    -- Support both new (nested) and legacy (flat) formats
    local source = data.config or data
    if type(source) == "table" then
        for k, v in pairs(DefaultConfig) do
            if source[k] ~= nil then
                mod.Config[k] = source[k]
            end
        end
        return true
    end
    return false
end

-- Save the config
function MagicConch_Config.Save(mod)
    -- Preserve existing runtime/state while updating config
    local data = loadAll(mod)
    data.config = mod.Config
    data.version = VERSION
    Isaac.SaveModData(mod, json.encode(data))
end

-- Runtime (per-run) persistence helpers
function MagicConch_Config.SaveRuntime(mod, runtime)
    local data = loadAll(mod)
    data.config = data.config or mod.Config or {}
    data.runtime = runtime or {}
    data.version = VERSION
    Isaac.SaveModData(mod, json.encode(data))
end

function MagicConch_Config.LoadRuntime(mod)
    local data = loadAll(mod)
    if type(data.runtime) == "table" then
        return data.runtime
    end
    return nil
end

-- Reset the config
function MagicConch_Config.Reset(mod)
    for k, v in pairs(DefaultConfig) do
        mod.Config[k] = v
    end
    MagicConch_Config.Save(mod)
end

---@type MagicConchConfig
return MagicConch_Config
