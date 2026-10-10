# MagicConch Language and Translation Add/Modify Guide

## Table of Contents

### Language and Translation Management
- [1. Add/Modify Languages (Code, Name, Font, etc.)](#1-addmodify-languages-code-name-font-etc)
- [2. Add/Modify Translation Strings](#2-addmodify-translation-strings)
- [3. Notes for Adding/Modifying Strings](#3-notes-for-addingmodifying-strings)
- [4. Example: Adding a New Message](#4-example-adding-a-new-message)
- [Summary](#summary)

### Magic Conch API Guide
- [Overview](#overview)
- [Detailed Implementation Guide](#detailed-implementation-guide)
  - [Step 1: Basic Structure Setup](#step-1-basic-structure-setup)
  - [Step 2: API Readiness Verification Function](#step-2-api-readiness-verification-function)
  - [Step 3: Callback Registration Function](#step-3-callback-registration-function)
  - [Step 4: Periodic Check System](#step-4-periodic-check-system)
  - [Step 5: Callback Registration and Backup System](#step-5-callback-registration-and-backup-system)
  - [Callback Processing Function Implementation](#callback-processing-function-implementation)
- [Quick Reference (Simple Usage)](#quick-reference-simple-usage)
- [result Table Structure](#result-table-structure)
- [API Function Reference](#api-function-reference)
- [Important Precautions](#important-precautions)
- [Magic Conch Operation Method](#magic-conch-operation-method)
- [ToDo](#todo)

---

## 1. Add/Modify Languages (Code, Name, Font, etc.)

Add or modify language tables in the `LANGUAGE_MAP` array in `magic_conch_lang.lua`.

```lua
local LANGUAGE_MAP = {
    { code = "EN", options = "en", name = "English", font = "gfx/font/EnglishFont.fnt" },
    { code = "KR", options = "kr", name = "Korean", font = "gfx/font/Kkubulim.fnt" },
    { code = "JP", options = "jp", name = "Japanese", font = "gfx/font/JapaneseFont.fnt" }, -- Example addition
    -- Add more as needed
}
```

- **code**: Language code (uppercase, e.g., "EN", "KR", "JP")
- **options**: String matching the game's Options.Language value (e.g., "en", "kr", "jp")
- **name**: Language name to display in the UI (e.g., "English", "Korean", "Japanese")
- **font**: Font path to use for this language (Implement Soon)

---

## 2. Add/Modify Translation Strings

Add or modify translation strings in the `MagicConchStrings` table for each language code.

```lua
local MagicConchStrings = {
    EN = {
        MaybeSomeday = {text = "Maybe someday.", type = "neutral"},
        -- ...etc...
    },
    KR = {
        MaybeSomeday = {text = "언젠가는 하겠죠.", type = "neutral"},
        -- ...etc...
    },
    JP = { -- Example addition
        MaybeSomeday = {text = "いつかきっと。", type = "neutral"},
        Nothing = {text = "なにもありません。", type = "negative"},
        -- Add more as needed
    }
}
```

- **EN, KR, JP** etc. must match the `code` in `LANGUAGE_MAP`.
- **text**: The actual string to display.
- **type**: Message type (e.g., "neutral", "positive", "negative"). __**2:2:1 ratio recommendation**__

---

## 3. Notes for Adding/Modifying Strings

- When you add a `code` to `LANGUAGE_MAP`, you must also add a corresponding table to `MagicConchStrings`.
- It is recommended to keep the same message keys (e.g., MaybeSomeday, Nothing, etc.) across all languages.
- When adding a new message, add the same key to all languages for consistency.

---

## 4. Example: Adding a New Message

```lua
-- Add the same key to all languages
EN = {
    ...,
    NewMessage = {text = "This is a new message.", type = "neutral"},
}
KR = {
    ...,
    NewMessage = {text = "이것은 새로운 메시지입니다.", type = "neutral"},
}
JP = {
    ...,
    NewMessage = {text = "これは新しいメッセージです。", type = "neutral"},
}
```

---

## Summary

1. Add/modify language info in `LANGUAGE_MAP`.
2. Add/modify translation strings in `MagicConchStrings` (`code` must match).
3. Use the same message keys for all languages.
4. Manage font paths in `LANGUAGE_MAP` as well.

---

## Magic Conch API Guide

### Overview

Magic Conch provides an API that allows other mods to utilize Magic Conch functionality. Other mods can execute Magic Conch or receive and process results.

### Detailed Implementation Guide

#### **Step 1: Basic Structure Setup**

**1.1 Mod Registration and Variable Initialization**
```lua
local YourMod = RegisterMod("Your Mod Name", 1)

-- API-related control variables
local apiCheckTimer = 0        -- Timer counter (frame units)
local maxRetries = 60          -- Maximum retry count (10 seconds = 60 * 1/6 seconds)
local retryCount = 0           -- Current retry count
YourMod.apiRegistered = false  -- API registration completion flag
```

**1.2 Check Interval Settings**
- `apiCheckTimer >= 10`: Check every 10 frames (about 1/6 second)
- `maxRetries = 60`: Total 10 seconds of attempts (60 times * 1/6 second)
- Game usually runs at 60FPS, so 10 frames = about 0.167 seconds

#### **Step 2: API Readiness Verification Function**

**2.1 Complete Readiness Check**
```lua
local function isMagicConchAPIReady()
    return MagicConch and                              -- 1. MagicConch mod exists
           MagicConch.API and                          -- 2. API object exists
           type(MagicConch.API) == "table" and         -- 3. API is table type
           MagicConch.API.RegisterCallback and         -- 4. RegisterCallback function exists
           type(MagicConch.API.RegisterCallback) == "function" and  -- 5. Function type check
           MagicConch.API.IsReady and                  -- 6. IsReady function exists
           type(MagicConch.API.IsReady) == "function" and          -- 7. Function type check
           MagicConch.API.IsReady()                    -- 8. Actual readiness check
end
```

**2.2 Verification Step Description**
1. **MagicConch**: Check basic mod object loading
2. **MagicConch.API**: Check API interface creation
3. **type() checks**: Verify objects are correct types
4. **Function existence check**: Verify required functions are defined
5. **IsReady() call**: Check Magic Conch internal initialization completion

#### **Step 3: Callback Registration Function**

**3.1 Registration Function Structure**
```lua
local function registerMagicConchAPI()
    Isaac.ConsoleOutput("Registering Magic Conch API callback...")
    
    local success = MagicConch.API.RegisterCallback(handleMagicConchResult, "Your Mod Name")
    if success then
        Isaac.ConsoleOutput("Magic Conch API callback registration successful!")
    else
        Isaac.ConsoleOutput("Magic Conch API callback registration failed!")
    end
end
```

**3.2 Callback Function Requirements**
- **Function signature**: `function(result)`
- **result parameter**: Magic Conch result table
- **modName**: Unique mod name (prevent duplicates)

#### **Step 4: Periodic Check System**

**4.1 Timer-based Check Logic**
```lua
local function apiRegistrationCallback()
    -- Check registration completion flag
    if not YourMod.apiRegistered then
        apiCheckTimer = apiCheckTimer + 1
        
        -- Execute every 10 frames (about 1/6 second)
        if apiCheckTimer >= 10 then
            apiCheckTimer = 0  -- Reset timer
            retryCount = retryCount + 1
            
            Isaac.ConsoleOutput("Checking API readiness... (Attempt " .. retryCount .. "/" .. maxRetries .. ")")
            
            if isMagicConchAPIReady() then
                -- Success: Register API and cleanup
                Isaac.ConsoleOutput("=== Magic Conch API Ready! ===")
                registerMagicConchAPI()
                YourMod.apiRegistered = true
                
                -- Important: Remove callback (performance optimization)
                YourMod:RemoveCallback(ModCallbacks.MC_POST_UPDATE, apiRegistrationCallback)
                
            elseif retryCount >= maxRetries then
                -- Failure: Give up and cleanup
                Isaac.ConsoleOutput("=== Warning: Magic Conch API initialization failed ===")
                YourMod.apiRegistered = true  -- Stop further attempts
                
                -- Remove callback (prevent infinite loop)
                YourMod:RemoveCallback(ModCallbacks.MC_POST_UPDATE, apiRegistrationCallback)
            end
        end
    end
end
```

**4.2 Timer Calculation Method**
- **Isaac Game**: Basic 60FPS
- **10 frames**: About 0.167 seconds (1/6 second)
- **60 attempts**: Total 10 seconds waiting
- **Reasonable interval**: Minimize CPU load

#### **Step 5: Callback Registration and Backup System**

**5.1 Main Registration System**
```lua
-- Start periodic checking
YourMod:AddCallback(ModCallbacks.MC_POST_UPDATE, apiRegistrationCallback)
```

**5.2 Backup Registration System (New Level)**
```lua
YourMod:AddCallback(ModCallbacks.MC_POST_NEW_LEVEL, function()
    if isMagicConchAPIReady() and not YourMod.apiRegistered then
        Isaac.ConsoleOutput("Attempting API registration on new level...")
        registerMagicConchAPI()
        YourMod.apiRegistered = true
    end
end)
```

**5.3 Backup System Necessity**
- **Game restart**: Provide additional opportunities
- **Level transition**: Re-check API status
- **Safety net** role

#### **Callback Processing Function Implementation**

**Callback Function Structure**
```lua
local function handleMagicConchResult(result)
    -- Result verification
    if not result or not result.text or not result.type then
        Isaac.ConsoleOutput("Error: Invalid Magic Conch result")
        return
    end
    
    Isaac.ConsoleOutput("Magic Conch Result: " .. result.text .. " (Type: " .. result.type .. ")")
    
    -- Type-based branching
    if result.type == "positive" then
        handlePositiveResult(result)
    elseif result.type == "negative" then
        handleNegativeResult(result)
    else -- "neutral"
        handleNeutralResult(result)
    end
end
```

**Callback Registration and Removal**
```lua
-- Register callback
MagicConch.API.RegisterCallback(handleMagicConchResult, "YourModName")

-- Remove callback (when needed)
MagicConch.API.UnregisterCallback("YourModName")
```

**Safe Callback with Error Handling**
```lua
local function safeMagicConchCallback(result)
    local success, err = pcall(function()
        if not result or not result.text or not result.type then
            return
        end
        
        -- Actual processing logic
        handleMagicConchResult(result)
    end)
    
    if not success then
        Isaac.ConsoleOutput("Magic Conch callback error: " .. tostring(err))
    end
end
```

---

### Quick Reference (Simple Usage)

For cases where Magic Conch is already loaded, here's a simple method:

```lua
if MagicConch and MagicConch.API and MagicConch.API.IsReady() then
    MagicConch.API.RegisterCallback(function(result)
        Isaac.ConsoleOutput("Magic Conch: " .. result.text .. " (" .. result.type .. ")")
    end, "MyMod")
end
```

**Note**: Use this method only when loading order is guaranteed. In most cases, it's safer to follow the **Detailed Implementation Guide** above.

### result Table Structure

Structure of the result table received in callback functions:

```lua
{
    text = "Magic Conch's answer",        -- string: Actual answer text
    type = "positive/negative/neutral",   -- string: Result type
    timestamp = 12345,                    -- number: Game frame number
    displayStyle = 1,                     -- number: Display style (0: Fortune, 1: Item)
    source = "Magic Conch",               -- string: Always "Magic Conch"
    version = "1.0"                       -- string: Magic Conch version
}
```

**Type-based Processing Guide:**
- **positive**: Positive effects (item upgrades, health recovery, etc.)
- **negative**: Negative effects (curse addition, item removal, etc.)
- **neutral**: Neutral effects (information display, logging, etc.)

### API Function Reference

#### **Callback-related API Functions**

| Function | Purpose | Input | Return Value |
|----------|---------|-------|--------------|
| `RegisterCallback(callback, modName)` | Register callback | function, string | boolean |
| `UnregisterCallback(modName)` | Remove callback | string | boolean |
| `TriggerMagicConch(modName)` | Execute Magic Conch | string | table |
| `PreviewResult(offset)` | Preview a future result in the current room without consuming a use | omitted or integer 0..1,000,000 | table or nil, error code |
| `IsReady()` | Check API readiness | - | boolean |
| `GetLastResult()` | Get last result | - | table/nil |
| `GetCallbackInfo()` | Get registered callback info | - | table |

### Preview results from another mod

```lua
local api = MagicConch and MagicConch.API
if api and api.IsReady() and type(api.PreviewResult) == "function" then
    local nextResult, errorCode = api.PreviewResult()
    if nextResult then
        print(nextResult.type)       -- "positive", "neutral", or "negative"
        print(nextResult.text)       -- Localized response
        print(nextResult.id)         -- Language-independent response ID
        print(nextResult.useNumber)  -- One-based use number in this room
    end
    local afterNext = api.PreviewResult(1)
end
```

Call with a dot, not a colon. `offset` defaults to 0 (the next unconsumed use); 1 means the following use. Returns a fresh `{id, text, type, usageCount, useNumber, offset}` table. `usageCount` is the count before the forecast draw; `useNumber = usageCount + 1`.

Previewing does not consume a use or RNG state, save data, activate effects, record diagnostic observations, or invoke callbacks. It works while disabled, busy, or at the room limit, but does not promise that activation is currently allowed. During an animation it forecasts the next unconsumed use, not the answer already in progress.

The forecast matches a later successful `TriggerMagicConch` while the run, room, probability/forced-reply settings and usage count remain unchanged. Query again after intervening activations or settings changes. Changing language translates the text while preserving the ID. Other-room queries are not supported.

Failure returns `nil, errorCode`: `API_NOT_READY`, `NO_ACTIVE_RUN`, `INVALID_OFFSET`, or `NO_RESPONSE`. Reload the updated mod before using this new function.

### Important Precautions

#### **Callback Processing Requirements**

1. **Always perform result verification**
   ```lua
   if not result or not result.text or not result.type then
       return  -- Ignore invalid results
   end
   ```

2. **Protect callbacks with pcall**
   ```lua
   local success, err = pcall(handleMagicConchResult, result)
   if not success then
       Isaac.ConsoleOutput("Callback error: " .. tostring(err))
   end
   ```

3. **Manage callback registration/removal**
   - On mod load: Call `RegisterCallback`
   - On mod unload: Call `UnregisterCallback`
   - Duplicate registration with same modName will overwrite

#### **Things to Avoid**

- Do not directly modify result table (read-only)
- Do not register new callbacks inside callback functions
- Do not ignore errors when they occur in callback functions
- Do not call TriggerMagicConch without checking Magic Conch status

### Magic Conch Operation Method

1. **Use**: Isaac lifts up the Magic Conch (uses MagicConch.png image)
2. **Start**: Slot machine sound + screen shake
3. **Wait**: Brief tension building
4. **Display**: Answer text display + type-based effects
5. **Cooldown**: Configurable cooldown time

**Type-based Effects:**
- **Positive**: Angel sound + Isaac happy face
- **Negative**: Isaac disgusted face + screen shake + (item removal in Delete Mode)
- **Neutral**: "Hmm..." sound

---

## ToDo

- How to make fonts
