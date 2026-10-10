-- Result text uses screen-space coordinates; native HUD coordinates are engine-owned.
local Display = {}

function Display.ValidCoordinate(value)
    return type(value) == "number" and value == value and value >= 0 and value <= 10000
end

function Display.Position(config)
    local position = config.resultPosition
    if type(position) == "table" and Display.ValidCoordinate(position.x) and Display.ValidCoordinate(position.y) then
        return { mode = "custom", x = position.x, y = position.y, anchor = "top_left" }
    end
    return { mode = "hud" } -- Do not invent coordinates for ShowItemText/ShowFortuneText.
end

function Display.CopyResult(result)
    if not result then return nil end
    local copy = {}
    for key, value in pairs(result) do
        if key == "position" and type(value) == "table" then
            copy.position = { mode = value.mode, x = value.x, y = value.y, anchor = value.anchor }
        else copy[key] = value end
    end
    return copy
end

return Display
