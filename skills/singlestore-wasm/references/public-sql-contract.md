# 공개 SQL 계약과 typed 생성 경로

DB 함수의 코드·이름·설명 입력에 적용한다. 지정 버전 공식 SQL 문서에서 호출 형태별 인자 순서·타입·기본값·반환값, NULL·빈 입력·경계·오류를 기록한다. 웹 문서의 메이저 버전과 정확한 패치 버전을 구분하고 고정 릴리스의 문서·SQL 등록 정의·SQL 진입 소스로 보완한다. 소스는 계산과 문서에 없는 동작의 근거다. 불일치는 기록하고 영향받는 계약을 확정하지 않는다. 독립적인 작업은 계속한다.

원본 공개 SQL에 없는 포인터·버퍼 길이·실행 컨텍스트·내부 제어값은 공개 인자나 JSON 원소로 노출하지 않는다. SQL 진입 함수가 내부 값을 어떻게 설정하는지 확인한다. 원본 SQL에서 공개하는 길이·옵션은 유지한다. 복합 값의 시작/끝/포함 경계 등 의미 정보는 내부 제어값과 구분하여 표현한다. generated 결과·starter는 원본 계약의 근거가 아니다.

## 공통 생성 규칙: 공개 호출 형태 전체 보존

1. 원본의 공식 API 문서, SQL 등록 정의, 호출 래퍼를 함께 조사한다. 입력받은 C 파일의 내부 함수 인자 수는 공개 호출 규격이 아니다. 공개 SQL이 없는 라이브러리는 해당 언어의 공개 API와 호출 경로를 기준으로 한다.
2. 사용자에게서 명시적인 범위 제한이 없으면 공개 호출 형태 전체를 `origin.forms`에 기록한다. 형태별 인자 순서·타입·개수·반환값, 생략 시 주입되는 기본값과 출처를 `feasibility.md`에 표로 남긴다. 가장 긴 호출만 선택하거나 이전 산출물을 원본 목록으로 사용하지 않는다.
3. 사용자 지정 JSON 호출은 우선한다. JSON 대체 시 원본 호출 형태마다 배열 길이·위치별 타입·기본값·매핑을 정의한다. 반복 조건은 반복 부분만 묶고 고정 인자를 유지한다. 내부 길이·포인터·제어값은 비공개로 둔다. 배열 길이가 다르다는 이유로 공개 함수를 여러 개 만들지 않는다.
4. 아래 CREATE AGGREGATE 예외를 제외하고 짧은 호출은 생성된 구현이 원본과 동일한 기본값을 채운다. 사용자가 기본값을 직접 입력하면 계산값이 같다는 이유로 짧은 호출을 제거하지 않는다. 지원 형태 축소는 일반적인 `calling_convention` 자동 진행의 대상이 아니며, 사용자 범위 제한 또는 별도 명시적 동의가 필요하다. 제외한 형태·이유·사용자 근거는 분석 표에 남긴다.
5. 원본 목록 → 계약 → 구현의 분기 → 독립 기대값 사례 → 생성 SQL을 형태별로 대조한다. 각 형태의 정상 입력, 생략 기본값, 명시적 NULL, 잘못된 길이·타입을 검증한다. 잘못된 길이는 원본이 허용하지 않는 길이만 거부한다. 특정 계산 경로의 대량 무작위 테스트를 모든 호출 형태의 검증으로 대신하지 않는다.

예를 들어 원본 호출 인자 수가 `{2,5}`라면 JSON 배열 길이도 `{2,5}`로 대응하고, 길이 2에서 생략 비용을 내부에서 채운다. 3·4개를 임의 허용하지 않는다. 이 수치는 예시이며 실제 허용 형태와 기본값은 매번 원본에서 확인한다.

`typed-scalar`와 공개 계약을 사용하는 HANDLE 빌드는 `check_form_coverage`로 선언된 모든 형태의 정상 입력 사례를 검사한다. JSON 형태는 배열 길이와 타입을 함께 사용해 유일하게 선택되어야 한다. SQL NULL 조기 반환·오류 사례·빈 집계만으로 형태가 검증됐다고 세지 않는다. 여러 형태를 고정 인자로 구현하는 별도 경로는 해당 분기 선택과 검증도 확장해야 한다. 이 검사는 에이전트가 원본 목록 자체를 누락했는지 알아낼 수 없으므로, 출처와 분석 표를 대조하는 검토를 생략하지 않는다.

## CREATE AGGREGATE의 DEFAULT 제약

문서의 지원 표기와 달리 현재 실제 동작에서는 CREATE AGGREGATE의 인자 DEFAULT를 지원하지 않는다. 집계 등록 SQL에 DEFAULT를 생성하지 않는다. 모든 집계 호출·사용 예시·검증 SQL에는 선언된 SQL 인자를 전부 명시한다. 원본에서 인자를 생략했다면 대상 호출에는 원본 기본값을 명시하고, 원본/대상 예시와 값을 `mappings`, `feasibility.md` 및 최종 입력 계약에 기록한다. 예를 들어 마지막 옵션의 원본 기본값이 `'[]'`라면 대상 호출에도 그 값을 마지막 인자로 전달한다.

이는 위의 짧은 호출 보존 규칙에 대한 집계 전용 예외다. 기본값의 명시적 전달만으로 계산 의미·반환 형식·공개 함수 개수가 유지되면 `calling_convention` 차이로 기록하고 이 정책을 근거로 별도 확인 없이 진행한다. 원본 `origin.forms`와 기본값 기록을 삭제하지 않는다. 일반 UDF의 CREATE FUNCTION에는 이 금지를 적용하지 않는다. JSON 내부의 생략 항목이나 구현 내부 기본값은 SQL 인자의 DEFAULT와 구분하며 기존 보존 규칙을 유지한다.

## 선택 순서

1. 고정 공개 인자는 구현 가능하면 개수·순서·의미를 유지한다.
2. 복수 호출 형태 및 반복 조건도 정확한 대상 패치·기능 설정·함수 종류에서 원본 형태를 제공할 수 있는지 먼저 확인한다. 문서상 오버로딩 지원을 해당 서버 또는 모든 Wasm/UDAF 경로의 성공으로 확대하지 않는다. 전역 설정을 자동 변경하지 않는다.
3. 제공하기 어렵거나 사용자가 JSON 호출을 명시하면 JSON_BUILD_ARRAY로 대체한다. 생성기의 미지원만으로 JSON을 선택하지 않는다. 반복 조건은 반복 부분만 묶으며 패턴·시간 등 고정 인자는 유지한다.
4. 원본 인자 수, 대상 SQL 인자 수, 배열 길이를 각각 기록한다. 같은 길이의 다른 타입 호출은 위치별 타입으로 선택하며 모호하면 오류다. {2,5} 길이는 3·4를 허용하지 않는다. 생략 기본값과 명시적 JSON null은 구분한다.
5. SQL 문법 호환과 계산 의미 호환을 별도 보고한다. 원본/대상 호출 예시와 차이를 적는다. 오류 발생 조건·분류와 코드/메시지의 동일 여부도 구분한다. 미정의 동작·메모리 오류 재현은 목표가 아니다.

## version 1 계약

`--contract`는 아래 필드를 갖는 JSON 파일이다. 원본 DB 이름·출처 등은 요청에서 확보한 실제 근거로 채운다. `tests/test_public_contract.py`는 실행 가능한 **합성 검증 fixture**이며 DB 문서의 대체 근거가 아니다.

- `version`: 1.
- `origin`: `database`, `version`, `documentation`, `nulls`, `empty`, `errors`, `boundaries`와 `forms`.
- `origin.forms[]`: 고유 `id`, `arguments`(순서대로 `name`, `type`, `meaning`, `default`), `returns`. `default: null`은 생략 기본값 없음이다. 실제 NULL 기본값은 `{"value": null}`처럼 구별하여 기록한다.
- `target`: 정확한 `version`, 기능·설정·사용자 지정의 `capability_evidence`, 순서대로 `arguments`(`name`, `abi`, `meaning`), `sql_null`.
- `mappings[]`: 원본 `form`마다 `bindings`(원본 공개 인자명 → `{"argument": "대상명"}` 또는 `{"argument":"배열명","index":0}`), 실제 `source_call`, `target_call`. 내부 인자는 여기에 넣지 않는다.
- `internal[]`: 내부 인자 `name`, 구성 방법/고정값의 `expression`, SQL 진입 경로의 `evidence`. 실행할 코드를 이 문자열에서 자동 생성하지 않는다. 구현과 소스 검토 및 테스트로 대응을 확인한다.
- `differences[]`: 기존 compatibility 형식의 공개 계약 차이와 accepted/evidence. 미합의 차이는 생성 전에 거부한다. 차이가 없으면 빈 목록.
- `representations[]`: 복합 값의 원본 의미·표현 형식·정밀도 보존·원본으로의 대응을 기록한다. 없으면 빈 목록.
- `json_arguments[]`: 아래 일반 JSON 전달 계약. 없으면 빈 목록.

`json_arguments`의 각 항목:

- `argument`: 대상 string 인자명. `reason`: 대체 필요 근거. `invalid`: `error`.
- `max_bytes`: 1..65535의 UTF-8 입력 상한. 실제 원본·자원 요구를 분석해 설정하고 추가 제한은 보고한다.
- `mode: forms`: `allowed_lengths`에 허용 길이를 명시. `variants[]`는 원본 `form`, 위치별 `items` 타입 스키마, 생략 시 적용할 `defaults` 객체. 누락 위치에 값을 채워 명시적 null을 덮어쓰지 않는다. 선택한 form과 defaults를 계산 로직에 별도로 전달한다.
- `mode: repeat`: `min_items`, `max_items`, 각 원소의 `items` 타입 스키마. 다른 고정 SQL 인자는 배열에 넣지 않는다.

타입 스키마는 `type`과 명시적 `nullable`을 요구한다. `string`, `boolean`, `integer`(i64 범위의 `min`/`max`), `number`(유한 double 범위의 `min`/`max`), `array`(`min_items`/`max_items`/`items`), `object`(`properties`, 모든 키 필수·추가 키 거부)를 지원한다. 일반 파싱은 serde_json 1.0.140의 arbitrary_precision 기능을 사용하며 정수 스키마는 i64로 정확히 검사한다. `number`는 f64 의미다. 고정소수점·날짜·시간·i64 외 정밀 수치는 문자열 등의 명시적 표현과 별도 계산/검증이 필요하다. 지원하지 않는 타입을 f64로 몰래 변환하지 않는다.

## 생성·빌드

`scaffold.py --shape typed-scalar --name <name> --contract <contract.json> --output <new-project>` 또는 `--shape typed-udaf`를 사용한다. 기존 출력 디렉터리는 거부한다. 원본 계약을 분석한 뒤에만 생성한다.

- scalar: Canonical ABI의 string/s32/s64/f64 혼합 고정 인자, 또는 string으로 전달하는 JSON 인자. 반환은 기존 검증 프로필인 BIGINT NULL, SQL NULL 전파. `logic::evaluate`는 Result<i64,String>이며 i64::MIN은 오류 sentinel로 예약된다. 정상 결과가 이 값일 수 있거나 NULL 정책·반환 타입이 다르면 이 프로필에 맞춰 의미를 바꾸지 말고 별도 ABI/오류/반환 경로를 확장한다. 오류는 현재 `invalid_input` 한 분류이며 DB 오류 코드/메시지 동등성을 주장하지 않는다.
- UDAF: 기존 HANDLE lifecycle을 유지하고 ITERATE 인자를 계약에서 생성한다. 입력은 NOT NULL, 반환 starter는 TEXT NOT NULL이다. 다른 원본 반환 계약은 기존 HANDLE 반환 프로필과 ABI를 함께 조정한다. `State`의 add/merge/render/encode/decode를 원본 의미로 구현한다. 내부 제어값·빈 그룹 정책은 starter에 넣지 않는다.
- JSON 경로는 `json_input.rs`와 pinned serde_json을 사용한다. 의존성을 준비하고 Cargo.lock을 보존한 뒤 기존 build.py의 offline 빌드를 실행한다. 기존 unsigned 정수·boolean·null 조건 파서는 변경하지 않는다.
- 계산 로직·독립 사례를 채운 후 `build.py`를 실행한다. typed scalar는 실제 Wasm으로 모든 비NULL 사례를 실행하고 NULL/SQL 오류 전달은 DB 검증으로 남긴다. UDAF는 기존 local_verify 또는 독립 callback 실행과 DB 검증을 사용한다.

case의 JSON 인자는 `{"json_array":["text",-1,1.25,true,null]}`로 적으면 SQL에서 JSON_BUILD_ARRAY로 생성한다. 복합 JSON 입력은 명시적인 JSON 문자열로 테스트한다. 중첩 값에 대한 SQL 생성 함수까지 검증된 것으로 주장하지 않는다. 원본과 대상 변환 중 정밀도 보존은 실제 DB 사례로 별도 확인한다.

## 구형 형식과 검증

기존 shape·manifest·조건 배열 템플릿은 유지하며 자동 변환하거나 사용자 생성물을 덮어쓰지 않는다. 신규 typed 경로만 public_contract version 1을 요구한다. 기존 프로젝트 전환은 별도 새 디렉터리에 원본 SQL 계약부터 작성하고 재생성·재검증한다. 기존 compatibility의 arity는 대상 SQL 인자 수로만 해석한다.

`tests/test_public_contract.py`는 계약/생성 회귀 검사다. `tests/smoke_public_contract.py --output <new-external-directory>`는 실제 혼합 scalar·JSON 호출 형태·복합 JSON·혼합 HANDLE starter를 빌드하고 Wasm으로 실행한다. 의존성 미준비 시 `--fetch`를 사용하면 cargo fetch를 먼저 실행한다. 출력은 저장소 밖에 둔다. 합성 fixture의 성공은 원본 DB 의미 동등성을 증명하지 않는다. 원본 DB 비교·SingleStore 등록/호출은 별도 상태로 보고한다.

원본/대상 어댑터는 사례 ID별 원본 인자·대상 인자·적용 기본값·결과/오류를 연결한다. 내부 C 실행만으로 SQL의 기본값·NULL·타입 변환을 검증했다고 하지 않는다. 원본 실행이 불가능해도 로컬 작업은 완료하고 원본 SQL 비교는 미검증으로 남긴다.
