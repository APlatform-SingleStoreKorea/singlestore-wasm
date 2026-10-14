# 호환성 차이와 사용자 확인

## 분석과 결정 순서

1. 코드·SQL·이전 대화에서 인자 수, 지원 범위, 이미 합의한 차이를 먼저 찾는다. 함수 이름이나 짧은 변환 요청만 받아도 스킬이 이를 분석한다. 사용자에게 내부 ABI, 메모리 전달 방식, Rust 타입 선택을 요구하지 않는다.
2. [compatibility.md](compatibility.md), 입력에 해당하는 참조 문서, 원본 함수의 공식 문서·소스와 대상 SingleStore 버전의 지원 범위를 확인한다. 기본은 9.1.1이며 문서와 실제 DB 검증을 구분한다. 템플릿 부재를 제품의 제한으로 단정하지 않는다.
3. 사용자에게 보이는 계약을 비교한다: 공개 함수 수, 호출 방식, 반환 형식, 계산 의미(NULL·오류·정밀도·입력 범위 포함). public wrapper 뒤의 비공개 core/콜백 수만 늘어나는 것은 공개 함수 수 변경이 아니다.
4. 코드·SQL에서 인자 수가 명확하거나 기존 대화에서 결정했으면 그 범위로 진행한다. 전체 지원을 명시했으면 전체 범위로 진행한다. 내부 구현 또는 호출 방식만 바뀌고 공개 함수 개수·반환 형식·계산 의미가 유지되면 질문하지 않는다. 새로 필요한 공개 함수 개수·반환 형식·계산 의미 변경은 차이와 선택지를 설명하고 답변을 받은 뒤 확정한다. 전체 지원은 반환 형식이나 계산 의미 변경 동의가 아니다.
5. 질문은 무엇이 달라지고 사용에 어떤 영향이 있는지 쉬운 말로 짧게 설명한 뒤 구체적인 선택지를 제시한다. 사용자가 모르면 사용하려는 SQL 또는 목적을 받아 적절한 범위를 제안한다. 이미 받은 답변을 재사용하고 반복 질문하지 않는다. 답변 전에도 공통 조사·분석·독립적인 작업은 계속하되 선택이 필요한 함수들을 임의로 확정·생성하거나 DB에 등록하지 않는다.

## 호출 방식 변경의 자동 진행

SingleStore 이식에 필요한 호출 방식 변경만으로는 사용자 확인을 요청하지 않는다. 함수명 변경, 인자 순서 조정, ClickHouse의 `f(parameters)(arguments)`를 단일 인자 목록으로 합치기, 반복 조건을 JSON 배열로 묶기처럼 공개 함수 개수·반환 형식·계산 의미가 유지되는 변경은 자동 진행한다. 예를 들어 `windowFunnel(window, mode)(timestamp, cond1, cond2)`를 `window_funnel(window, mode, timestamp, JSON_BUILD_ARRAY(cond1, cond2))`로 옮기는 호출 문법 변경은 확인 없이 진행한다.

사용자가 기존 호출 유지나 특정 시그니처를 명시했으면 그 요구를 우선한다. 전처리나 타입 변환이 NULL·오류·정밀도·입력 범위·옵션 동작을 바꾸면 호출 방식 변경으로만 분류하지 말고 `semantics` 차이를 별도로 기록하여 확인한다. 공개 함수 개수와 반환 형식 변경도 각각 기존 확인 절차를 따른다.

결정 기록에는 `calling_convention` 차이를 남기고 `accepted: true`로 설정한다. `evidence`에는 이 절의 정책 경로와 계산 의미·반환 형식·공개 함수 개수가 유지되는 근거를 적는다. 이는 사용자 지정 기본 정책의 적용이며 새 승인 대화를 했다는 뜻이 아니다. 최종 결과에는 변경 전후 호출 예시를 제공한다.

## 반복되는 가변 조건: JSON 배열 기본

반복되는 조건은 행별 JSON_BUILD_ARRAY로 묶고 공개 함수 하나를 생성한다. 지원할 조건 개수는 다시 묻지 않는다. 고정 인자 호출을 명시한 사용자만 기존 조건별 범위 절차를 적용한다. 일반 다중 인자와 패턴·시간 등 역할이 다른 인자는 유지한다.

compatibility의 available_arities/selected_arities는 **SQL 인자 수**다. retention JSON 방식은 `[1]`이고, 런타임 조건 개수는 별도 condition_array.min_items/max_items로 기록한다. 이것을 조건 1개 지원으로 해석하지 않는다. public_variants는 `[""]`다. 원본 문서/소스가 불일치하면 고정 버전의 실제 소스를 조사하고 한계를 기록한다.

retention의 JSON 조건 배열 입력에서는 입력 행이 전혀 없어 조건 수를 알 수 없는 집계에 `[]`를 반환하는 것을 사용자 지정 기본 정책으로 적용한다. 이 경우 빈 입력 정책을 다시 묻지 않는다. 원본의 조건 수만큼 0을 반환하는 동작과의 차이는 결과와 검증 보고서에 명시한다. 결정 기록의 해당 `semantics` 차이는 `accepted: true`로 기록하고, `evidence`에는 이 Skill의 [retention 빈 입력 기본 정책](json-condition-array.md#retention-빈-입력-기본-정책)을 근거로 적는다. 실제로 하지 않은 새 승인 대화를 만들지 않는다.

사용자가 다른 빈 입력 결과 또는 고정 인자 호출을 명시하면 그 계약을 우선한다. retention의 반환은 [반환 기본 정책](json-condition-array.md#retention-반환-기본-정책)에 따라 JSON 직렬화/TEXT 계약을 적용하고 해당 return_format 차이를 accepted: true로 기록한다. 빈 입력과 이 반환 정책은 다시 묻지 않는다. 다른 함수의 빈 입력 의미나 반환 타입 변경까지 이 정책으로 승인하지 않는다. 그 밖의 미합의 공개 계약 변경은 기존 확인 절차를 따른다.

## 실행 가능한 결정 기록

에이전트가 분석 결과를 다음 JSON으로 기록한다. 사용자가 JSON을 작성할 필요는 없다. `available_arities`는 이 요청에서 분석한 지원 가능 범위이고, `selected_arities`는 명확한 코드·SQL 또는 사용자 선택이다. 불명확하면 `null`로 두고 질문한다. `"all"`은 사용자가 전체 지원을 명시한 경우에만 사용한다. 코드의 `*args`는 특정 개수 선택 근거가 아니다.

```json
{
  "target_version": "9.1.1",
  "review_basis": ["feasibility.md: 원본 문서·대상 버전 지원 확인과 출처"],
  "available_arities": [3, 7],
  "selected_arities": [3, 7],
  "scope_basis": {"source": "user", "evidence": "조건별 별도 함수 설명 후 사용자: 3개와 7개"},
  "differences": []
}
```

`scope_basis.source`는 `code`, `sql`, `conversation`, `user` 중 하나다. 기존 대화 근거는 실제 합의 내용이나 메시지 위치를 보존한다. 내부 구현 차이는 `feasibility.md`에 기록하며 `differences`에는 공개 계약의 차이만 넣는다. 각 차이는 다음 형태다.

```json
{
  "aspect": "return_format",
  "original": "배열",
  "proposed": "JSON 문자열",
  "impact": "SQL에서 배열 대신 JSON을 해석해야 함",
  "accepted": false,
  "evidence": ""
}
```

`aspect`는 `public_function_count`, `calling_convention`, `return_format`, `semantics` 중 하나다. 실제 답변·기존 합의 또는 이 문서의 사용자 지정 기본 정책이 적용될 때 해당 차이의 `accepted`를 `true`로 하고 `evidence`에 근거를 기록한다. 명확한 인자 수에 맞춘 고정 인자 구현 자체는 추가 범위 질문을 만들지 않는다. 별도의 이름 변경·전처리 등 호출 변경은 위 자동 진행 정책으로 판단하며, 계산 의미 변경이 동반되면 별도로 확인한다. 함수 범위 질문에서 이미 설명하고 선택한 함수 분리는 그 답변으로 기록하며 다시 묻지 않는다. 전체 지원 답변을 다른 차이의 승인 근거로 복사하지 않는다.

```bash
python <skill>/scripts/compatibility.py <request-plan.json>
```

종료 코드 0의 `ready`일 때만 반환된 `selected_arities`에 포함된 프로젝트를 생성한다. `needs_user_input`(종료 코드 2)이면 `selected_arities` 출력은 빈 목록이며 `pending`에 필요한 결정이 남는다. 조사한 후보 전체를 생성 대상으로 쓰지 않는다. 이 도구는 자연어/SQL 분석기나 사용자 동의 인증기가 아니다. 근거의 진실성 및 누락된 차이 검토는 에이전트 책임이다.

새 생성·계약 변경 요청은 결정 기록을 `function.json`의 `compatibility`에 넣는다. scalar scaffold는 `--compatibility <request-plan.json>`으로 생성 전에 검사하고 삽입한다. 수동 UDAF 구현도 새 작업 디렉터리에 같은 필드를 넣고 빌드한다. UDAF는 `compatibility.public_variants`에 선택한 공개 aggregate suffix 목록(예: `[""]`)을 추가한다. 공통 manifest 검사는 실제 인자 수가 선택 범위 안에 있는지와 `aggregates`가 선택 목록과 정확히 같은지 확인한다. 반복 조건 개수는 JSON 배열 길이로 표현하고 SQL 인자 수와 구분한다. 사용자가 고정 인자를 명시한 경우 해당 계약을 따른다.

미확정 기록은 scaffold·build·SQL 생성·DB 연결 전에 차단되며, 선택 범위 변경은 manifest 해시가 바뀌므로 재빌드가 필요하다. `status.py`에도 선택 범위와 차이를 표시한다. 기존 배포 프로젝트/고정 fixture의 재현을 위해 기록이 없는 예전 manifest는 계속 지원한다. 이 호환 경로를 새 요청의 분석·확인 생략 수단으로 사용하지 않는다.

최종 답변의 기존 `입력 계약과 제한`에 선택한 지원 범위와 원본 대비 차이·합의 근거를 넣는다. 기존 Wasm/Base64/SQL 링크, 등록 대상과 함수, 실행 환경 표는 유지한다. `feasibility.md`와 `verification.md`에 자세한 근거와 실제 생성·등록 대상만 남긴다.
