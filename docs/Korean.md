## 📑 목차

### 언어 및 번역 관리
- [1. 언어(코드, 이름, 폰트 등) 추가/수정](#1-언어코드-이름-폰트-등-추가수정)
- [2. 번역 문장 추가/수정](#2-번역-문장-추가수정)
- [3. 문장 추가/수정 시 주의사항](#3-문장-추가수정-시-주의사항)
- [4. 예시: 새로운 문장 추가](#4-예시-새로운-문장-추가)
- [요약](#요약)

### Magic Conch API 가이드
- [개요](#개요)
- [세부 구현 가이드](#세부-구현-가이드)
  - [1단계: 기본 구조 설정](#1단계-기본-구조-설정)
  - [2단계: API 준비 상태 검증 함수 구현](#2단계-api-준비-상태-검증-함수-구현)
  - [3단계: 콜백 등록 함수 구현](#3단계-콜백-등록-함수-구현)
  - [4단계: 주기적 확인 시스템 구현](#4단계-주기적-확인-시스템-구현)
  - [5단계: 콜백 등록 및 백업 시스템](#5단계-콜백-등록-및-백업-시스템)
  - [콜백 처리 함수 구현](#콜백-처리-함수-구현)
- [빠른 참조 (Simple Usage)](#빠른-참조-simple-usage)
- [result 테이블 구조](#result-테이블-구조)
- [API 함수 참조](#api-함수-참조)
- [중요 주의사항](#중요-주의사항)
- [Magic Conch 동작 방식](#magic-conch-동작-방식)
- [추가예정](#추가예정)

---

## 1. 언어(코드, 이름, 폰트 등) 추가/수정

`magic_conch_lang.lua`의 `LANGUAGE_MAP` 배열에 새로운 언어 테이블을 추가하거나, 기존 값을 수정하면 됩니다.

```lua
local LANGUAGE_MAP = {
    { code = "EN", options = "en", name = "English", font = "gfx/font/EnglishFont.fnt" },
    { code = "KR", options = "kr", name = "Korean", font = "gfx/font/Kkubulim.fnt" },
    { code = "JP", options = "jp", name = "Japanese", font = "gfx/font/JapaneseFont.fnt" }, -- 추가 예시
    -- 필요시 더 추가
}
```

- **code**: 언어 코드(대문자, 예: "EN", "KR", "JP")
- **options**: 게임 Options.Language 값과 매칭되는 문자열(예: "en", "kr", "jp")
- **name**: UI에 표시될 언어 이름(예: "English", "Korean", "Japanese")
- **font**: 해당 언어에 사용할 폰트 경로 (추후 구현 예정)

---

## 2. 번역 문장 추가/수정

`MagicConchStrings` 테이블에서 각 언어 코드에 해당하는 테이블에 문장을 추가/수정하면 됩니다.

```lua
local MagicConchStrings = {
    EN = {
        MaybeSomeday = {text = "Maybe someday.", type = "neutral"},
        -- ...생략...
    },
    KR = {
        MaybeSomeday = {text = "언젠가는 하겠죠.", type = "neutral"},
        -- ...생략...
    },
    JP = { -- 추가 예시
        MaybeSomeday = {text = "いつかきっと。", type = "neutral"},
        Nothing = {text = "なにもありません。", type = "negative"},
        -- 필요시 더 추가
    }
}
```

- **EN, KR, JP** 등은 `LANGUAGE_MAP`의 `code`와 반드시 일치해야 함
- **text**: 실제로 표시될 문장
- **type**: 문장 타입(예: "neutral", "positive", "negative") __**2:2:1 비율 추천**__

---

## 3. 문장 추가/수정 시 주의사항

- `LANGUAGE_MAP`에 `code`를 추가하면, `MagicConchStrings`에도 동일한 `code`로 번역 테이블을 추가해야 함
- 문장 키(예: MaybeSomeday, Nothing 등)는 모든 언어에서 동일하게 맞추는 것이 좋음
- 새로운 문장 추가 시, 모든 언어에 해당 키를 추가하는 것이 권장됨

---

## 4. 예시: 새로운 문장 추가

```lua
-- 모든 언어에 동일한 키로 추가
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

## 요약

1. `LANGUAGE_MAP`에 언어 정보 추가/수정
2. `MagicConchStrings`에 번역 문장 추가/수정 (`code` 일치 필수)
3. 문장 키는 모든 언어에서 동일하게 맞추는 것이 좋음
4. 폰트 경로 등도 `LANGUAGE_MAP`에서 관리

---

## Magic Conch API 가이드

### 개요

Magic Conch는 다른 모드들이 Magic Conch의 기능을 활용할 수 있도록 API를 제공합니다. 다른 모드에서 Magic Conch를 실행하거나, 결과를 받아서 처리할 수 있습니다.

### 세부 구현 가이드

#### **1단계: 기본 구조 설정**

**1.1 모드 등록 및 변수 초기화**
```lua
local YourMod = RegisterMod("Your Mod Name", 1)

-- API 관련 제어 변수들
local apiCheckTimer = 0        -- 타이머 카운터 (프레임 단위)
local maxRetries = 60          -- 최대 재시도 횟수 (10초 = 60 * 1/6초)
local retryCount = 0           -- 현재 재시도 횟수
YourMod.apiRegistered = false  -- API 등록 완료 플래그
```

**1.2 체크 주기 설정**
- `apiCheckTimer >= 10`: 10프레임마다 확인 (약 1/6초)
- `maxRetries = 60`: 총 10초간 시도 (60회 * 1/6초)
- 게임은 보통 60FPS이므로 10프레임 = 약 0.167초

#### **2단계: API 준비 상태 검증 함수 구현**

**2.1 완전한 준비 상태 확인**
```lua
local function isMagicConchAPIReady()
    return MagicConch and                              -- 1. MagicConch 모드 존재
           MagicConch.API and                          -- 2. API 객체 존재
           type(MagicConch.API) == "table" and         -- 3. API가 테이블 타입
           MagicConch.API.RegisterCallback and         -- 4. RegisterCallback 함수 존재
           type(MagicConch.API.RegisterCallback) == "function" and  -- 5. 함수 타입 확인
           MagicConch.API.IsReady and                  -- 6. IsReady 함수 존재
           type(MagicConch.API.IsReady) == "function" and          -- 7. 함수 타입 확인
           MagicConch.API.IsReady()                    -- 8. 실제 준비 상태 확인
end
```

**2.2 검증 단계별 설명**
1. **MagicConch**: 기본 모드 객체 로딩 확인
2. **MagicConch.API**: API 인터페이스 생성 확인
3. **type() 검사**: 객체가 올바른 타입인지 확인
4. **함수 존재 확인**: 필요한 함수들이 정의되었는지 확인
5. **IsReady() 호출**: Magic Conch 내부 초기화 완료 확인

#### **3단계: 콜백 등록 함수 구현**

**3.1 등록 함수 구조**
```lua
local function registerMagicConchAPI()
    Isaac.ConsoleOutput("Magic Conch API 콜백 등록 중...")
    
    local success = MagicConch.API.RegisterCallback(handleMagicConchResult, "Your Mod Name")
    if success then
        Isaac.ConsoleOutput("Magic Conch API 콜백 등록 성공!")
    else
        Isaac.ConsoleOutput("Magic Conch API 콜백 등록 실패!")
    end
end
```

**3.2 콜백 함수 요구사항**
- **함수 시그니처**: `function(result)`
- **result 매개변수**: Magic Conch 결과 테이블
- **modName**: 고유한 모드 이름 (중복 방지)

#### **4단계: 주기적 확인 시스템 구현**

**4.1 타이머 기반 확인 로직**
```lua
local function apiRegistrationCallback()
    -- 등록 완료 플래그 확인
    if not YourMod.apiRegistered then
        apiCheckTimer = apiCheckTimer + 1
        
        -- 10프레임(약 1/6초)마다 실행
        if apiCheckTimer >= 10 then
            apiCheckTimer = 0  -- 타이머 리셋
            retryCount = retryCount + 1
            
            Isaac.ConsoleOutput("API 준비 상태 확인 중... (시도 " .. retryCount .. "/" .. maxRetries .. ")")
            
            if isMagicConchAPIReady() then
                -- 성공: API 등록 및 정리
                Isaac.ConsoleOutput("=== Magic Conch API 준비됨! ===")
                registerMagicConchAPI()
                YourMod.apiRegistered = true
                
                -- 중요: 콜백 제거 (성능 최적화)
                YourMod:RemoveCallback(ModCallbacks.MC_POST_UPDATE, apiRegistrationCallback)
                
            elseif retryCount >= maxRetries then
                -- 실패: 포기 및 정리
                Isaac.ConsoleOutput("=== 경고: Magic Conch API 초기화 실패 ===")
                YourMod.apiRegistered = true  -- 더 이상 시도하지 않음
                
                -- 콜백 제거 (무한 루프 방지)
                YourMod:RemoveCallback(ModCallbacks.MC_POST_UPDATE, apiRegistrationCallback)
            end
        end
    end
end
```

**4.2 타이머 계산 방식**
- **Isaac 게임**: 기본 60FPS
- **10프레임**: 약 0.167초 (1/6초)
- **60회 시도**: 총 10초간 대기
- **적당한 간격**: CPU 부하 최소화

#### **5단계: 콜백 등록 및 백업 시스템**

**5.1 메인 등록 시스템**
```lua
-- 주기적 확인 시작
YourMod:AddCallback(ModCallbacks.MC_POST_UPDATE, apiRegistrationCallback)
```

**5.2 백업 등록 시스템 (새 레벨)**
```lua
YourMod:AddCallback(ModCallbacks.MC_POST_NEW_LEVEL, function()
    if isMagicConchAPIReady() and not YourMod.apiRegistered then
        Isaac.ConsoleOutput("새 레벨에서 API 등록 시도...")
        registerMagicConchAPI()
        YourMod.apiRegistered = true
    end
end)
```

**5.3 백업 시스템 필요성**
- **게임 재시작** 시 추가 기회 제공
- **레벨 전환** 시 API 상태 재확인
- **안전장치** 역할

#### **콜백 처리 함수 구현**

**콜백 함수 구조**
```lua
local function handleMagicConchResult(result)
    -- 결과 검증
    if not result or not result.text or not result.type then
        Isaac.ConsoleOutput("오류: 잘못된 Magic Conch 결과")
        return
    end
    
    Isaac.ConsoleOutput("Magic Conch 결과: " .. result.text .. " (타입: " .. result.type .. ")")
    
    -- 타입별 분기 처리
    if result.type == "positive" then
        handlePositiveResult(result)
    elseif result.type == "negative" then
        handleNegativeResult(result)
    else -- "neutral"
        handleNeutralResult(result)
    end
end
```

**콜백 등록 및 해제**
```lua
-- 콜백 등록
MagicConch.API.RegisterCallback(handleMagicConchResult, "YourModName")

-- 콜백 해제 (필요시)
MagicConch.API.UnregisterCallback("YourModName")
```

**오류 처리가 포함된 안전한 콜백**
```lua
local function safeMagicConchCallback(result)
    local success, err = pcall(function()
        if not result or not result.text or not result.type then
            return
        end
        
        -- 실제 처리 로직
        handleMagicConchResult(result)
    end)
    
    if not success then
        Isaac.ConsoleOutput("Magic Conch 콜백 오류: " .. tostring(err))
    end
end
```

---

### 빠른 참조 (Simple Usage)

Magic Conch가 이미 로드된 경우에만 사용하는 간단한 방법:

```lua
if MagicConch and MagicConch.API and MagicConch.API.IsReady() then
    MagicConch.API.RegisterCallback(function(result)
        Isaac.ConsoleOutput("Magic Conch: " .. result.text .. " (" .. result.type .. ")")
    end, "MyMod")
end
```

**주의**: 이 방법은 로딩 순서가 보장된 경우에만 사용하세요. 대부분의 경우 위의 **세부 구현 가이드**를 따르는 것이 안전합니다.

### result 테이블 구조

콜백 함수에서 받는 result 테이블의 구조:

```lua
{
    text = "Magic Conch 답변",        -- string: 실제 답변 텍스트
    type = "positive/negative/neutral", -- string: 결과 타입
    timestamp = 12345,                -- number: 게임 프레임 번호
    displayStyle = 1,                 -- number: 표시 스타일 (0: Fortune, 1: Item)
    source = "Magic Conch",           -- string: 항상 "Magic Conch"
    version = "1.0"                   -- string: Magic Conch 버전
}
```

**타입별 처리 가이드:**
- **positive**: 긍정적 효과 (아이템 업그레이드, 체력 회복 등)
- **negative**: 부정적 효과 (저주 추가, 아이템 제거 등)
- **neutral**: 중립적 효과 (정보 표시, 로그 등)

### API 함수 참조

#### **콜백 관련 API 함수**

| 함수 | 용도 | 입력 | 반환값 |
|------|------|------|--------|
| `RegisterCallback(callback, modName)` | 콜백 등록 | function, string | boolean |
| `UnregisterCallback(modName)` | 콜백 해제 | string | boolean |
| `TriggerMagicConch(modName, options)` | 일반 또는 답변 지정 실행 | string, 선택적 table | table |
| `PreviewResult(offset, options)` | 현재 방의 결과 미리보기 (횟수 소비 없음) | 선택적 정수 0~1,000,000, 선택적 table | table 또는 nil, 오류 코드 |
| `GetCurrentRoomUsage()` | 현재 방의 성공한 활성화 횟수 | - | number 또는 nil, 오류 코드 |
| `GetResultPosition()` | 다음 결과의 표시 방식·좌표 | - | table 또는 nil, 오류 코드 |
| `SetResultPosition(x, y)` | 결과 텍스트 화면 좌표 설정·저장 | number, number | boolean, 오류 코드 |
| `ResetResultPosition()` | 게임 기본 HUD 표시로 복원·저장 | - | boolean, 오류 코드 |
| `IsReady()` | API 준비 상태 확인 | - | boolean |
| `GetLastResult()` | 마지막 결과 조회 | - | table/nil |
| `GetCallbackInfo()` | 등록된 콜백 정보 | - | table |

### 다른 모드에서 결과 미리보기

```lua
local api = MagicConch and MagicConch.API
if api and api.IsReady() and type(api.PreviewResult) == "function" then
    local nextResult, errorCode = api.PreviewResult() -- 다음 성공한 사용
    if nextResult then
        print(nextResult.type)       -- "positive" / "neutral" / "negative"
        print(nextResult.text)       -- 현재 언어의 문구
        print(nextResult.id)         -- 언어와 무관한 문구 ID
        print(nextResult.useNumber)  -- 이 방에서 몇 번째 사용인지 (1부터)
    end
    local afterNext = api.PreviewResult(1) -- 그다음 사용
end
```

`.`으로 호출합니다. `offset`은 현재 미소비 횟수로부터 얼마나 뒤를 볼지이며 기본값 0입니다. 반환값은 `{id, text, type, forced, usageCount, useNumber, offset}`입니다. `usageCount`는 추첨 직전 횟수이고 `useNumber = usageCount + 1`입니다. 각 호출은 새 테이블을 반환합니다. `options`에는 아래 실행 함수와 같은 답변 지정을 넣을 수 있습니다.

조회는 사용 횟수·RNG 상태를 소비하지 않고 저장, 애니메이션, 소리, 관측 로그, 등록 콜백을 실행하지 않습니다. 비활성화, 연출 진행 중, 방별 횟수 제한 상태에서도 예상 결과를 계산할 수 있지만 실제 활성화 가능 여부를 뜻하지는 않습니다. 연출 중에는 이미 시작한 답변이 아니라 **다음 미소비 사용**의 답변입니다.

방·런·확률/강제 응답 설정·사용 횟수가 그대로라면 이후 성공한 `TriggerMagicConch` 결과와 일치합니다. 다른 사용이 끼어들거나 설정이 바뀌면 다시 조회하세요. 언어를 바꾸면 문구는 번역되고 ID는 같습니다. 다른 방 조회는 지원하지 않습니다.

실패하면 `nil, errorCode`를 반환합니다: `API_NOT_READY`(초기화 전), `NO_ACTIVE_RUN`(런 없음), `INVALID_OFFSET`(잘못된 인자), `NO_RESPONSE`(사용 가능한 문구 없음). 새 함수를 사용하려면 수정된 모드를 다시 불러와야 합니다.

### 사용 횟수와 결과 텍스트 위치

API가 준비된 런에서 호출합니다.

```lua
local api = MagicConch.API
local used, errorCode = api.GetCurrentRoomUsage()
local ok, errorCode = api.SetResultPosition(160, 80)
local position = api.GetResultPosition()
-- {mode="custom", x=160, y=80, anchor="top_left"}
-- api.ResetResultPosition() -- 기본 게임 HUD로 복원
```

횟수 조회는 값을 바꾸지 않습니다. 초기화 전이나 런이 없으면 `nil, "API_NOT_READY"` 또는 `nil, "NO_ACTIVE_RUN"`을 반환합니다. 일반·강제 실행 모두 성공한 활성화만 1회씩 포함합니다.

좌표는 **Isaac 화면 좌표**, 결과 첫 줄의 좌상단입니다. 유한한 0~10,000 숫자(소수 포함)를 허용합니다. 잘못된 입력은 `false, "INVALID_POSITION"`으로 실패하고 설정을 바꾸지 않습니다. 화면 밖 좌표는 자동 보정하지 않으므로 호출 모드에서 화면 크기에 맞춰 배치하세요. 아이콘·횟수 표시 위치는 별개입니다.

좌표 설정은 재시작 후에도 유지되고 **다음 활성화부터** 적용됩니다. 진행 중인 답변은 활성화 시점의 좌표·표시 스타일을 유지합니다. 기본 모드는 `{mode="hud"}`를 반환합니다. 기본 HUD 좌표는 엔진이 관리하므로 `x/y`를 반환하지 않습니다. 좌표를 직접 관리하려면 `SetResultPosition`으로 custom 모드를 사용하세요.

custom 모드는 모드의 한국어 지원 폰트로 `timing.display` 동안 표시합니다. `displayStyle=0`은 답변 한 줄, `1`은 답변과 유형 부제목입니다. 방 이동 시 표시가 끝납니다. 폰트가 로드되지 않으면 기본 HUD로 출력하며 최종 콜백과 `GetLastResult().position`에 실제 모드 `{mode="hud"}`를 전달합니다. `GetResultPosition()`은 다음 활성화에 요청할 설정을 나타냅니다.

### 답변을 정해서 실행하기

다음 예시는 각각 별도의 호출 방식입니다. 연출 중에는 추가 실행이 거절되므로 하나씩 호출하세요.

```lua
-- 유형만 고정: 해당 유형 안에서 문구는 방·횟수 기반으로 선택
local result = MagicConch.API.TriggerMagicConch("OtherMod", {type="positive"})
-- 기존 ID 고정: 현재 언어의 번역 사용
-- local result = MagicConch.API.TriggerMagicConch("OtherMod", {id="Yes"})
-- 직접 문구와 유형 지정
-- local result = MagicConch.API.TriggerMagicConch("OtherMod", {
--     type="neutral", text="이번에는 기다려."
-- })
if not result.success then print(result.reason) end

-- 같은 옵션으로 미리보기 가능
local forecast, errorCode = MagicConch.API.PreviewResult(0, {id="No"})
```

지원 옵션은 `{type=...}`, `{id=...}`, `{type=..., text=...}`입니다. 생략하거나 `{}`이면 기존 추첨을 사용합니다. 유형은 대소문자를 구분하지 않는 `positive/neutral/negative`입니다. ID는 대소문자를 구분하고 다른 필드와 함께 지정할 수 없습니다. 직접 문구는 공백만이 아닌 유효한 UTF-8 한 줄, 최대 256자이며 줄바꿈·탭·제어 문자는 허용하지 않습니다. 직접 문구의 `id`는 nil입니다.

기본 ID: `Yes`, `Absolutely`, `Definitely`, `OfCourse`, `FollowTheConch`, `ConchKnowsAll`, `YouMay`, `Proceed`, `Nothing`, `Neither`, `IDontThinkSo`, `No`, `DontEvenAsk`, `NotToday`, `Forbidden`, `Impossible`, `AskAgainLater`, `UncertainTimes`, `MaybeSomeday`, `TryAgain`.

지정은 **이번 호출에만** 적용되고 `Config.forcedReply`나 확률 설정을 바꾸지 않습니다. 전역 강제 유형보다 호출별 지정이 우선합니다. 성공 시 횟수 1회를 소비하고 연출·유형별 효과(부정의 Delete Mode 포함)·콜백은 정상 실행합니다. 비활성화, 연출 중, 쿨다운, 방 사용 제한을 우회하지 않습니다. 이후 일반 추첨은 증가한 사용 횟수를 사용합니다.

`pendingResult`, 최종 콜백, `GetLastResult()`에는 `id`, `forced`, `position`도 포함됩니다. `forced=true`는 호출별 지정을 뜻합니다. 각 반환값과 각 콜백은 복사본을 받아, 수정해도 다른 콜백이나 실제 표시 결과에 영향을 주지 않습니다. 최종 `position`은 실제 표시 위치, `pendingResult.position`은 요청한 위치입니다.

잘못된 옵션은 횟수나 쿨다운을 소비하지 않습니다. 실행은 `{success=false, reason=...}`, 미리보기는 `nil, errorCode`로 실패합니다. 옵션 오류는 `INVALID_RESPONSE_OPTIONS`, `CONFLICTING_RESPONSE_OPTIONS`, `INVALID_RESPONSE_ID`, `INVALID_RESPONSE_TYPE`, `INVALID_RESPONSE_TEXT`입니다. 실행 제한은 `ROOM_LIMIT`, `COOLDOWN`이며, 기타 비활성/연출 중 실패는 기존 설명 문자열을 유지합니다.

`mc watch`는 호출별 강제 답변을 확률 표본에서 제외하고 `FORCED_EXCLUDED`/`excludedForced`로 셉니다. 전역 강제 유형은 이전처럼 해당 설정의 별도 관측 구간으로 집계합니다.

렌더링 API 근거: [Font.DrawStringUTF8](https://wofsauge.github.io/IsaacDocs/rep/Font.html#drawstringutf8), [게임 HUD](https://wofsauge.github.io/IsaacDocs/rep/HUD.html).

### 중요 주의사항

#### **콜백 처리 필수 사항**

1. **결과 검증 반드시 수행**
   ```lua
   if not result or not result.text or not result.type then
       return  -- 잘못된 결과 무시
   end
   ```

2. **pcall로 콜백 보호**
   ```lua
   local success, err = pcall(handleMagicConchResult, result)
   if not success then
       Isaac.ConsoleOutput("콜백 오류: " .. tostring(err))
   end
   ```

3. **콜백 등록/해제 관리**
   - 모드 로드 시: `RegisterCallback` 호출
   - 모드 언로드 시: `UnregisterCallback` 호출
   - 동일한 modName으로 중복 등록 시 덮어씌워짐

#### **피해야 할 사항**

- result 테이블 직접 수정 (읽기 전용)
- 콜백 내부에서 새로운 콜백 등록
- 콜백 함수 내에서 오류 발생 시 무시
- Magic Conch 상태 확인 없이 TriggerMagicConch 호출

---

### Magic Conch 동작 방식

1. **사용**: Isaac이 Magic Conch를 들어올림 (MagicConch.png 이미지 사용)
2. **시작**: 슬롯머신 소리 + 화면 흔들림
3. **대기**: 잠시 긴장감 조성
4. **표시**: 답변 텍스트 표시 + 타입별 효과
5. **쿨다운**: 설정 가능한 쿨다운 시간

**타입별 효과:**
- **Positive**: 천사 소리 + Isaac 행복한 얼굴
- **Negative**: Isaac 찡그린 얼굴 + 화면 흔들림 + (Delete Mode 시 아이템 삭제)
- **Neutral**: "흠..." 소리

---

## 추가예정

- 폰트 제작 방법
