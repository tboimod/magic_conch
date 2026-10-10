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
| `TriggerMagicConch(modName)` | Magic Conch 실행 | string | table |
| `PreviewResult(offset)` | 현재 방의 다음 결과 미리보기 (횟수 소비 없음) | 생략 또는 0~1,000,000 정수 | table 또는 nil, 오류 코드 |
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

`.`으로 호출합니다. `offset`은 현재 미소비 횟수로부터 얼마나 뒤를 볼지이며 기본값 0입니다. 반환값은 `{id, text, type, usageCount, useNumber, offset}`입니다. `usageCount`는 그 추첨 직전의 사용 횟수이고 `useNumber = usageCount + 1`입니다. 각 호출은 새 테이블을 반환합니다.

조회는 사용 횟수·RNG 상태를 소비하지 않고 저장, 애니메이션, 소리, 관측 로그, 등록 콜백을 실행하지 않습니다. 비활성화, 연출 진행 중, 방별 횟수 제한 상태에서도 예상 결과를 계산할 수 있지만 실제 활성화 가능 여부를 뜻하지는 않습니다. 연출 중에는 이미 시작한 답변이 아니라 **다음 미소비 사용**의 답변입니다.

방·런·확률/강제 응답 설정·사용 횟수가 그대로라면 이후 성공한 `TriggerMagicConch` 결과와 일치합니다. 다른 사용이 끼어들거나 설정이 바뀌면 다시 조회하세요. 언어를 바꾸면 문구는 번역되고 ID는 같습니다. 다른 방 조회는 지원하지 않습니다.

실패하면 `nil, errorCode`를 반환합니다: `API_NOT_READY`(초기화 전), `NO_ACTIVE_RUN`(런 없음), `INVALID_OFFSET`(잘못된 인자), `NO_RESPONSE`(사용 가능한 문구 없음). 새 함수를 사용하려면 수정된 모드를 다시 불러와야 합니다.

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
