# 함수 분석과 구현

## 판단과 계약

1. 작업 디렉터리, 적용 AGENTS.md, 기존 파일과 도구를 확인한다. 새 출력 디렉터리를 사용하고 기존 구현을 덮어쓰지 않는다.
2. 함수 이름·설명 또는 코드를 분석해 새 프로젝트를 생성한다. [compatibility.md](compatibility.md)와 참조 함수의 공식 문서·필요한 원본 소스를 확인하고 함수별 `feasibility.md`를 만든다. 참조 버전, 동작·입출력·옵션·기본값·경계 사례와 출처를 기록하고 대상 SingleStore의 지원 범위에 대응시킨다. 입력/출력/NULL, 함수 형태(UDF/UDAF/TVF), Unicode·정밀도·순서 의미, ABI/WIT, 외부 의존성, 메모리·시간·모듈 한도를 기록한다.
3. 가능 / 조건부 가능 / 불가 및 근거를 구분한다. **현재 스킬의 템플릿 부재는 SingleStore의 구현 불가능을 뜻하지 않는다.** 필요한 연결 코드·템플릿·빌드/검증 도구의 확장 가능성을 검토하고, 구현 가능한 미구현 부분은 이어서 작성한다. ABI 구현 또는 DB 검증이 남았다는 이유만으로 로컬 작업을 중단하지 않는다. 문서만으로 미확인인 항목을 성공으로 적지 않는다. v9.1 문서는 서버의 정확한 패치 버전과 동일하다고 가정하지 않는다.
4. 함수 설명·원본 코드로부터 기대값을 먼저 정한다. 빌드 후 실제값에 맞춰 기대값을 변경하지 않는다. 코드 입력은 파일/네트워크/프로세스/스레드/FFI/난수·시간 등 외부 의존성과 라이브러리 호출부터 검토한다. 원본에 정의된 동작을 우선하며, 미정의 NULL은 기본적으로 전파하고 잘못된 입력·비유한 결과는 명시적 오류로 처리한다. 경계값은 원본의 관찰 가능한 계산 의미를 보존한다. 기본 정책·오류 매핑·지원 입력 범위를 최종 `입력 계약과 제한`에 표시한다. 원본에 정의된 반환·계산 의미를 바꾸는 오류 매핑, 수학적 확장·오류 수정·입력 축소는 크기에 관계없이 사용자 확인 대상이다. 합리적인 기본값이라는 이유로 변경 동의를 대신하지 않는다.

## 가변 조건 입력

동일한 의미의 반복 조건을 받는 가변 인자는 기본적으로 행별 `JSON_BUILD_ARRAY(...)` 하나로 묶는다. 조건 개수를 묻거나 개수별 공개 함수를 생성하지 않는다. 사용자가 고정 인자/기존 호출 유지를 명시하면 우선한다. Levenshtein의 두 문자열, Black–Scholes의 서로 다른 인자는 유지한다. sequenceMatch/sequenceCount는 패턴·시간을 유지하고 반복 조건 부분만 배열로 묶는다. 자세한 설정·템플릿·빈 입력 결정은 [JSON 조건 배열](json-condition-array.md)을 읽는다. 이 기본 호출 설계 자체를 다시 승인받지 않는다. retention의 JSON 입력에서 입력 행이 없어 조건 수를 알 수 없으면 같은 문서의 사용자 지정 `[]` 기본 정책을 적용하며 다시 묻지 않는다. 그 밖의 미합의 반환 의미 변경은 구체적 차이만 확인한다.

## 생성과 구현

이름·설명 기반 요청은 [원본 출처와 실행 비교](reference-verification.md)를 따른다. 공식 문서 및 원본 소스의 실제 참조 링크·버전·커밋과 확보 여부를 기록한다. 기본 기대값은 고정 원본 코드 또는 원본 엔진을 실행해 생성하며, AI가 원본을 읽고 작성한 기대값은 독립 원본 실행 증거가 아니다. 동일 입력·기대값을 Wasm과 DB 검증에 사용한다. 원본 실행 불가 시 이유를 기록하고 빌드는 계속하되 의미 검증은 미검증으로 보고한다.

`<skill>`은 이 문서의 상위 디렉터리에서 SKILL.md가 있는 Skill 루트이며 명령은 그 위치의 실제 경로로 실행한다.

```bash
python3 <skill>/scripts/scaffold.py --name my_function --shape string-pair-i64 --compatibility <resolved-plan.json> --output <new-project>
```

현재 starter shape:

- `json-array-udaf`: TEXT 배열 입력과 TEXT 반환의 HANDLE UDAF 연결 코드 및 공통 조건 배열 파서. 계산·상태·직렬화·입력 정책·독립 기대값은 새 요청에 맞춰 구현한다. 조건 수·NULL·빈 입력 정책과 과거 참조/승인/검증 자료는 포함하지 않는다. 다른 반환 계약은 ABI와 함께 조정한다.

- `string-pair-i64`: UTF-8 문자열 둘 → i64. `src/logic.rs`에 `pub fn evaluate(left: &str, right: &str) -> i64`를 구현한다.
- `i64-unary`: i64 하나 → i64. `pub fn evaluate(value: i64) -> i64`를 구현한다. 오버플로 계약을 명시한다.
- `f64-scalar`: f64 인자 1~16개 → f64. `scaffold.py --shape f64-scalar --arguments s k t r sigma --name my_function --output <new-project>`처럼 원본 순서의 인자 이름을 지정한다. BASIC ABI와 SQL DOUBLE을 사용하며 실수 오차·Python 비교 설정은 [실수형 공용 프로필](python-porting.md#실수형-공용-프로필)을 따른다.

모든 scalar starter는 public SQL wrapper가 NULL을 먼저 전파한다. 반환·입력 타입이나 NULL 계약이 다른 요청을 이 형태로 억지 변환하지 않는다. 원본 함수의 옵션·집계·순서·상태 의미를 임의로 생략하거나 축소하지 않는다. [abi.md](abi.md)를 참고해 필요한 Rust 연결 코드, WIT, Cargo 설정, SQL 템플릿과 빌드·검증 경로를 확장한다. 기존 scripts의 shape/manifest/시그니처 검사도 확인하며 WIT나 템플릿만 바꾸고 호환된다고 가정하지 않는다. 숫자 및 명시적 TEXT 입력 HANDLE UDAF는 [공통 집계 프로필](common-pipeline.md)로 같은 build.py/db_verify.py를 사용한다. 다른 UDAF/TVF에는 필요한 프로필 확장을 구현한다. 새 형태는 테스트·컴파일하고 DB 검증 여부를 별도로 보고한다.

`src/logic.rs`와 의미 있는 Rust 테스트를 작성한다. `function.json`에 아래 형태의 독립 기대값을 채운다.

```json
{"id":"example", "args":["a","b"], "expected":1}
```

NULL은 JSON `null`, 반복 문자열은 `{"repeat":"a","count":4096}`로 표현한다. 오류 사례는 `expected` 대신 `expected_error`에 식별 가능한 메시지를 쓴다. 오류 sentinel이 필요하면 `error_sentinel`과 `error_message`를 설정한다. 정상 결과와 겹치는 sentinel을 사용하지 않는다.

문자열 길이를 제한한다면 `max_codepoints`를 설정해 wrapper가 Wasm 할당 전에 검사하게 하고 Rust에서도 방어한다. 기존 정수 반환 프로필의 출력 SQL은 BIGINT NULL이며 문자 인자는 utf8mb4를 명시한다. SQL 함수명은 Wasm export `evaluate`와 독립적이다.

공통 실행기는 함수별 로직과 분리한다. 집계 함수의 의미와 상태 직렬화는 Rust에 구현하고, 콜백·독립 기대값·분산 검증 자료를 manifest에 선언한다. 함수별 Python 빌드/등록 실행기를 새로 복제하지 않는다.
