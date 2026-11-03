# JSON 조건 배열과 HANDLE 입력 계약

원본 호출 유지 가능성을 먼저 확인한다. JSON 대체가 필요한 동일한 의미의 반복 조건은 행별 `JSON_BUILD_ARRAY(...)` 하나로 묶는다. 역할이 다른 인자는 유지한다. 공개 함수 하나로 여러 배열 길이를 받되 지원 범위와 그룹 내 길이 일치 여부는 계산 의미에 따라 결정한다. 원본 계약의 반복 범위를 기록한다. 사용자가 명시한 고정 호출은 우선한다.

```bash
python <skill>/scripts/scaffold.py --name my_aggregate --shape json-array-udaf --output new-project
```

선택을 확정한 새 요청의 `--compatibility request-plan.json`을 전달할 수 있다. SQL arity는 1이고 public_variants는 `[""]`다. scaffold는 공통 ABI, WIT와 `json_array.rs`를 제공한다. `logic.rs`의 State(Default + Clone), add, merge, render, encode, decode와 독립 테스트를 작성한다. 미구현 상태는 compile_error로 빌드를 차단한다. 원본 출처·정책·기대값·승인·검증 성공은 복사하지 않는다.

## 파서와 정책의 분리

`json_array::parse(text, min_items, max_items, max_bytes)`는 flat JSON 배열의 unsigned u64 정수·boolean·null을 그대로 반환한다. truthiness, UInt8 제한, 행 스킵, 빈 그룹 결과를 결정하지 않는다. 빈 배열과 32개 초과도 전달한 한도에 따라 처리한다. 문자열·중첩·소수 등 다른 JSON 원소가 필요하면 파서와 테스트를 확장한다. 임의 JSON 전체를 지원하는 파서로 주장하지 않는다.

manifest의 `condition_array`는 미정(null)으로 시작한다. 구현 전에 argument_index, min_items(0 이상), max_items, max_json_bytes, empty_result(결과 정책 설명), json_null(skip_row/reject/preserve), sql_null을 명시한다. Rust 파서에 같은 한도를 전달하고 함수별 정책을 구현·테스트한다. NULL 보존은 파서 기능이며 실제 계산 정책은 함수 로직이 정한다. 입력 없는 그룹과 길이 0 배열은 별도로 결정한다. 빈 입력·NULL·반환 형식은 원본 계약과 현재 요청으로 정하며 과거 요청의 승인을 상속하지 않는다.

## 입력 및 반환 ABI

현재 공통 HANDLE TEXT ABI는 `input_contracts`에 abi=string, sql_type=TEXT, charset=utf8mb4, collation=utf8mb4_bin, nullable=false를 명시한다. sql_null=not_null은 이 프로필의 기술적 제약이지 모든 JSON 함수의 의미 정책이 아니다. SQL NULL 지원 요청에는 wrapper 또는 ABI 확장과 별도 검증이 필요하다. JSON/LONGTEXT를 TEXT와 바꾸지 않는다. 반환 TEXT도 선택한 starter 계약이며 요청에 맞춰 반환 ABI·WIT·SQL을 함께 검토한다.

```sql
SELECT my_aggregate(JSON_BUILD_ARRAY(cond1, cond2)) FROM events;
SELECT my_aggregate(JSON_BUILD_ARRAY(cond1, cond2, cond3)) FROM events;
SELECT my_aggregate(JSON_BUILD_ARRAY(cond1, cond2, cond3, cond4, cond5)) FROM events;
```

WIT string은 ITERATE의 handle/pointer/length로 내려가며 manifest·WIT·Wasm export·SQL 참조를 함께 검사한다. 원본 엔진의 Nullable adapter에는 함수 자체와 다른 인자 제한이 있을 수 있다. 실제 NULL 열에만 Nullable을 적용하고 버전별 제한을 조사한다. 특정 실행의 오류 코드나 성공 결과를 모든 환경으로 확대하지 않는다. 원본 실행 비교와 Rust/Wasmtime/DB 검증은 각각 기록한다.


문자열·음수·실수·복합 값 또는 비연속 허용 길이는 이 조건 파서에 추가하지 않고 [공개 SQL 계약](public-sql-contract.md)의 typed 경로를 사용한다. 기존 파서와 manifest는 유지한다.
