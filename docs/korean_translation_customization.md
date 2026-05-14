# ERPNext 한국어 번역 커스터마이징

ERPNext의 한국어 번역 중 어색한 표현을 수정하는 방법을 정리한다.

---

## 번역 우선순위

ERPNext는 아래 순서로 번역을 로드하며, **나중에 로드된 것이 앞의 것을 덮어쓴다.**

| 우선순위 | 출처 | 위치 |
|:---:|---|---|
| 1 (낮음) | Frappe 기본 번역 | `apps/frappe/frappe/translations/ko.csv` |
| 2 | ERPNext 번역 | `apps/erpnext/erpnext/translations/ko.csv` |
| 3 (높음) | 사용자 번역 (DB) | Translation DocType |

---

## 권장 방법: Translation DocType 사용

DB에 저장되므로 `bench update` 시 ERPNext가 업그레이드되어도 수정 내용이 유지된다.

### 등록 방법

1. ERPNext 관리자 계정으로 로그인
2. 검색창에 **Translation** 입력 후 이동
3. **New** 버튼 클릭 후 아래와 같이 입력

| 필드 | 값 |
|---|---|
| **Language** | `ko` (Korean) |
| **Source Text** | 원문 영어 문자열 (화면에 표시되는 영어 그대로) |
| **Translated Text** | 원하는 한국어 표현 |
| **Context** | 비워도 됨 (동일 원문이 여러 맥락에서 쓰일 때만 사용) |

4. **Save**

> **주의:** Language를 `en` (English)으로 설정하면 적용되지 않는다.
> 반드시 `ko`로 선택해야 한다.

### 저장 후 적용

저장 시 번역 캐시가 자동으로 클리어된다.
브라우저에서 **Ctrl+Shift+R** (강력 새로고침)을 하면 즉시 반영된다.

---

## 비권장 방법: CSV 파일 직접 수정

`apps/erpnext/erpnext/translations/ko.csv` 또는
`apps/frappe/frappe/translations/ko.csv`를 직접 편집하는 방법이다.

**단점:** `bench update`로 ERPNext를 업그레이드하면 파일이 덮어써져 수정 내용이 사라진다.

수정 후에는 캐시를 수동으로 클리어해야 한다.

```bash
bench clear-cache
```

---

## 트러블슈팅

번역을 등록했는데 적용이 안 될 경우 아래 순서로 확인한다.

1. **강력 새로고침** — Ctrl+Shift+R 또는 Ctrl+F5
2. **Source Text 일치 여부 확인** — 브라우저 콘솔에서 실제 원문 확인
   ```js
   frappe.boot.lang_dict["확인할 영어 원문"]
   // 결과가 undefined면 원문이 다른 것
   ```
3. **Language 필드 확인** — `ko`로 설정되어 있는지 재확인

---

## Context 필드란

동일한 영어 원문이 화면의 여러 위치에서 다른 의미로 쓰일 때 구분하기 위한 값이다.
대부분의 경우 비워두면 된다.

내부적으로 Context가 있으면 조회 키를 `"source_text:context"` 형태로 만들고,
없으면 `"source_text"`만으로 매칭한다.
