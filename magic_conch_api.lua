-- ========================================
-- Magic Conch API Module
-- Provides interface for other mods to interact with Magic Conch
-- ========================================

local MagicConch_API = {}

-- Internal references (will be set by core module)
local MagicConch = nil
local gameState = nil
local getTiming = nil
local MagicConch_Lang = nil
local MagicConch_Config = nil

-- Initialize API with references from core module
function MagicConch_API.Init(magicConchMod, gameStateRef, getTimingFunc, langModule, configModule)
    MagicConch = magicConchMod
    gameState = gameStateRef
    getTiming = getTimingFunc
    MagicConch_Lang = langModule
    MagicConch_Config = configModule
end

-- Check if Magic Conch is available
local function isAvailable()
    return gameState.canInput and gameState.state == "idle" and MagicConch.Config.enabled
end

-- Execute Magic Conch sequence (shared between hotkey and API trigger)
-- @param triggerSource string - Source of trigger (e.g., "hotkey", "API: ModName")
-- @return boolean - Success or failure
local function executeMagicConchSequence(triggerSource)
    local limit = MagicConch.Config.attemptsPerRoom or 0
    if limit > 0 and MagicConch:GetCurrentRoomUsage() >= limit then return false end
    local currentTime = Game():GetFrameCount()
    
    -- Spam protection
    if currentTime - gameState.lastInputTime < 10 then 
        MagicConch.printDebug("Spam protection triggered (" .. triggerSource .. ")")
        return false
    end
    
    gameState.lastInputTime = currentTime
    gameState.canInput = false
    
    -- Get random answer
    local randomData = MagicConch_Lang.getRandomString(MagicConch.Config)
    if not randomData then
        MagicConch.printError("Failed to get random string")
        gameState.canInput = true
        return false
    end

    -- Optional observation only; a diagnostic failure must not interrupt gameplay.
    if MagicConch.RNGDiagnostics and MagicConch.RNGDiagnostics.Observe then
        local ok, err = pcall(MagicConch.RNGDiagnostics.Observe, randomData, triggerSource)
        if not ok then MagicConch.printError("RNG observation failed: " .. tostring(err)) end
    end
    
    -- Set pending data
    gameState.pendingText = randomData.text
    gameState.pendingType = randomData.type
    
    -- Start sequence with slot machine sound and Magic Conch holding animation
    local sfxManager = SFXManager()
    sfxManager:Play(SoundEffect.SOUND_COIN_SLOT)
    Game():ShakeScreen(5)
    
    -- Show Magic Conch holding animation with custom sprite
    local player = Isaac.GetPlayer(0)
    if player then
        -- Create custom sprite for Magic Conch using Isaac's basic collectible
        local sprite = Sprite()
        
        -- Try the most basic approach - use Isaac's default collectible animation
        local loadSuccess = pcall(function()
            -- Load without loading graphics immediately (false)
            sprite:Load("gfx/005.100_collectible.anm2", false)
            
            local texturePath = "gfx/MagicConch.png"
            
            sprite:ReplaceSpritesheet(1, texturePath)
            sprite:LoadGraphics()
            sprite:SetFrame("Idle", 0)
            sprite:Update()
        end)
        
        if not loadSuccess then
            -- Ultimate fallback - empty sprite
            sprite = Sprite()
            if MagicConch.Config.debugMode then
                MagicConch.printDebug("Using empty sprite as fallback")
            end
        else
            if MagicConch.Config.debugMode then
                MagicConch.printDebug("Successfully loaded Isaac collectible with Magic Conch texture")
            end
        end
        
        -- Animate holding the Magic Conch
        player:AnimatePickup(sprite, false, "Pickup")
        
        if MagicConch.Config.debugMode then
            MagicConch.printDebug("Magic Conch pickup animation started")
        end
    end
    
    gameState.state = "shaking"
    gameState.timer = 0
    MagicConch:RecordRoomUse()
    
    if MagicConch.Config.debugMode then
        MagicConch.printDebug("Started Magic Conch sequence (" .. triggerSource .. "): " .. gameState.pendingText)
    end
    
    return true
end

-- Execute callback function (internal use)
local function executeCallbacks(result)
    if not gameState.callbacks or #gameState.callbacks == 0 then
        MagicConch.printDebug("No callbacks registered")
        return
    end
    
    MagicConch.printDebug("Executing " .. #gameState.callbacks .. " registered callbacks")
    
    -- Create a safe copy of the result to prevent modification
    local safeResult = {
        text = result.text,
        type = result.type,
        timestamp = result.timestamp,
        displayStyle = result.displayStyle,
        -- Add additional metadata
        source = "Magic Conch",
        version = MagicConch_Config and MagicConch_Config.VERSION or "unknown"
    }
    
    local successCount = 0
    local errorCount = 0
    
    for i, callbackData in ipairs(gameState.callbacks) do
        local ok, err = pcall(function()
            if type(callbackData.func) == "function" then
                callbackData.func(safeResult)
                return true
            else
                error("Callback is not a function")
            end
        end)
        
        if ok then
            successCount = successCount + 1
            MagicConch.printDebug("Callback executed successfully for: " .. (callbackData.modName or "unknown"))
        else
            errorCount = errorCount + 1
            MagicConch.printError("Callback error for " .. (callbackData.modName or "unknown") .. ": " .. tostring(err))
            
            -- Remove invalid callbacks
            if string.find(tostring(err), "not a function") then
                MagicConch.printError("Removing invalid callback for: " .. (callbackData.modName or "unknown"))
                table.remove(gameState.callbacks, i)
            end
        end
    end
    
    MagicConch.printDebug("Callback execution complete - Success: " .. successCount .. ", Errors: " .. errorCount)
end

-- ===== Public API Functions =====

-- Preview a future result in the current room without activating or consuming a use.
-- offset=0 (default): next unconsumed use; offset=1: the use after that.
-- Available even while busy/disabled/at the room limit; not an activation guarantee.
-- Returns a fresh {id, text, type, usageCount, useNumber, offset}, or nil, errorCode.
function MagicConch_API.PreviewResult(offset)
    if not (MagicConch and gameState and MagicConch_Lang) then
        return nil, "API_NOT_READY"
    end
    if offset == nil then offset = 0 end
    if type(offset) ~= "number" or not math.tointeger(offset) or offset < 0 or offset > 1000000 then
        return nil, "INVALID_OFFSET"
    end
    if Game():GetNumPlayers() == 0 then return nil, "NO_ACTIVE_RUN" end

    local context = MagicConch_Lang.getRandomContext()
    context.usageCount = context.usageCount + math.tointeger(offset)
    local response = MagicConch_Lang.sample(MagicConch.Config, context)
    if not response then return nil, "NO_RESPONSE" end
    return { id = response.id, text = response.text, type = response.type,
        usageCount = context.usageCount, useNumber = context.usageCount + 1, offset = math.tointeger(offset) }
end

-- Register callback to receive Magic Conch results from other mods
-- @param callback function(result) - Function to receive the result
-- @param modName string - Mod name (optional)
-- @return boolean - Success or failure
--
-- Output/Debug Messages:
-- - Success: "Callback registered for: [modName]" (debug log)
-- - Error: "RegisterCallback: callback must be a function" (error log)
function MagicConch_API.RegisterCallback(callback, modName)
    -- Validate inputs
    if type(callback) ~= "function" then
        MagicConch.printError("RegisterCallback: callback must be a function, got " .. type(callback))
        return false
    end
    
    -- Default mod name if not provided
    if not modName or type(modName) ~= "string" or modName == "" then
        modName = "Unknown Mod"
    end
    
    -- Check for duplicate registrations from the same mod
    for i, existingCallback in ipairs(gameState.callbacks) do
        if existingCallback.modName == modName then
            MagicConch.printDebug("Replacing existing callback for: " .. modName)
            gameState.callbacks[i] = {
                func = callback,
                modName = modName,
                registeredTime = Game():GetFrameCount(),
                id = existingCallback.id or math.random(1000000)
            }
            return true
        end
    end
    
    -- Create new callback registration
    local callbackData = {
        func = callback,
        modName = modName,
        registeredTime = Game():GetFrameCount(),
        id = math.random(1000000) -- Unique ID for debugging
    }
    
    table.insert(gameState.callbacks, callbackData)
    MagicConch.printDebug("Callback registered for: " .. modName .. " (ID: " .. callbackData.id .. ")")
    MagicConch.print("API: " .. modName .. " has been connected to Magic Conch!")
    return true
end

-- Trigger Magic Conch (programming style)
-- @param modName string - Mod name that called this function
-- @return table - Result information
function MagicConch_API.TriggerMagicConch(modName)
    local result = {
        success = false,
        reason = "",
        estimatedTime = 0,
        pendingResult = nil
    }
    
    if not isAvailable() then
        if not MagicConch.Config.enabled then
            result.reason = "Magic Conch is disabled"
        elseif gameState.state ~= "idle" then
            result.reason = "Magic Conch is busy (state: " .. gameState.state .. ")"
            -- Calculate remaining time until completion
            local timing = getTiming()
            if gameState.state == "shaking" then
                result.estimatedTime = timing.shake - gameState.timer + timing.wait + timing.display
            elseif gameState.state == "waiting" then
                result.estimatedTime = timing.wait - gameState.timer + timing.display
            elseif gameState.state == "displaying" then
                result.estimatedTime = timing.display - gameState.timer
            elseif gameState.state == "cooldown" then
                result.estimatedTime = timing.cooldown - gameState.timer
            end
        else
            result.reason = "Magic Conch is not ready"
        end
        
        MagicConch.printDebug("TriggerMagicConch failed: " .. result.reason .. " (called by " .. (modName) .. ")")
        return result
    end
    
    -- Execute Magic Conch
    local triggerSource = "API: " .. (modName)
    local executeSuccess = executeMagicConchSequence(triggerSource)
    
    if not executeSuccess then
        result.reason = "Failed to execute Magic Conch sequence"
        return result
    end
    
    -- Set success information
    result.success = true
    result.reason = "Magic Conch activated successfully"
    local timing = getTiming()
    result.estimatedTime = timing.shake + timing.wait + timing.display
    result.pendingResult = {
        text = gameState.pendingText,
        type = gameState.pendingType,
        willDisplayIn = timing.shake + timing.wait
    }
    
    MagicConch.printDebug("Magic Conch triggered by: " .. (modName))
    return result
end

-- Execute registered callbacks (called by core module)
function MagicConch_API.ExecuteCallbacks(result)
    executeCallbacks(result)
end

-- Execute Magic Conch sequence (called by core module for hotkey)
function MagicConch_API.ExecuteMagicConchSequence(triggerSource)
    return executeMagicConchSequence(triggerSource)
end

-- Remove callback registration
-- @param modName string - Mod name to remove
-- @return boolean - Success or failure
function MagicConch_API.UnregisterCallback(modName)
    if not modName or type(modName) ~= "string" then
        MagicConch.printError("UnregisterCallback: modName must be a string")
        return false
    end
    
    for i = #gameState.callbacks, 1, -1 do
        if gameState.callbacks[i].modName == modName then
            table.remove(gameState.callbacks, i)
            MagicConch.printDebug("Callback unregistered for: " .. modName)
            return true
        end
    end
    
    MagicConch.printDebug("No callback found to unregister for: " .. modName)
    return false
end

-- Get callback information
-- @return table - List of registered callbacks
function MagicConch_API.GetCallbackInfo()
    local info = {
        count = #gameState.callbacks,
        callbacks = {}
    }
    
    for i, callbackData in ipairs(gameState.callbacks) do
        table.insert(info.callbacks, {
            modName = callbackData.modName,
            id = callbackData.id,
            registeredTime = callbackData.registeredTime,
            isValid = type(callbackData.func) == "function"
        })
    end
    
    return info
end

-- Get last result
-- @return table - Last Magic Conch result or nil
function MagicConch_API.GetLastResult()
    return gameState.lastResult
end

-- Create public API interface
function MagicConch_API.CreateInterface()
    return {
        -- Register callback: Allow other mods to receive Magic Conch results
        -- Input: callback (function), modName (string, optional)
        -- Output: boolean (success or failure)
        RegisterCallback = function(callback, modName) 
            return MagicConch_API.RegisterCallback(callback, modName) 
        end,
        
        -- Unregister callback: Remove callback registration
        -- Input: modName (string)
        -- Output: boolean (success or failure)
        UnregisterCallback = function(modName)
            return MagicConch_API.UnregisterCallback(modName)
        end,
        
        -- Trigger Magic Conch: Execute Magic Conch programmatically
        -- Input: modName (string, optional)
        -- Output: table { success, reason, estimatedTime, pendingResult }
        TriggerMagicConch = function(modName) 
            return MagicConch_API.TriggerMagicConch(modName) 
        end,

        -- Read-only preview; offset=0 means the next unconsumed use in this room.
        PreviewResult = function(offset)
            return MagicConch_API.PreviewResult(offset)
        end,
        
        -- Check if API is ready
        -- Output: boolean (ready or not)
        IsReady = function()
            return MagicConch ~= nil and 
                   gameState ~= nil and 
                   getTiming ~= nil and 
                   MagicConch_Lang ~= nil and 
                   MagicConch_Config ~= nil
        end,
        
        -- Get callback information
        -- Output: table { count, callbacks }
        GetCallbackInfo = function()
            return MagicConch_API.GetCallbackInfo()
        end,
        
        -- Get last result
        -- Output: table or nil
        GetLastResult = function()
            return MagicConch_API.GetLastResult()
        end,
        
        -- Get current state
        -- Output: string (state name)
        GetState = function()
            return gameState.state
        end,
        
        -- Version information
        Version = MagicConch_Config and MagicConch_Config.VERSION,
        
        -- Config information (read-only)
        Config = MagicConch and MagicConch.Config
    }
end

return MagicConch_API
