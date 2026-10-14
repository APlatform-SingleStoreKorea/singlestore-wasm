# Python 코드 입력과 Rust 이식

사용자는 코드와 “이걸 SingleStore Wasm으로 변환해줘”만 제공한다. 함수 이름·설명만 주는 경로와 기존 Rust 입력도 유지한다. 아래 선택은 Codex가 수행한다. 사용자가 ABI나 Rust 타입을 배우거나 지정해야 진행되는 구조로 만들지 않는다.

## 분석과 의미 보존

원본을 `tests/reference.py`에 보존한다. 실행 전에 최상위 코드·함수·호출 의존성의 부수 효과를 읽고 확인한다. Python 함수 인자 순서, 스칼라/배열 사용, 자료형, 반환, import 및 외부 호출을 분석한다. 예제 호출에서 스칼라 의미가 명확하면 SQL 한 행당 scalar를 기본으로 하고 배열 지원 여부를 명시한다. 배열 전용 동작을 스칼라로 몰래 축소하지 않는다. 적용 가능성·의존성 대체·타입·지원 범위를 `feasibility.md`에 기록한다.

Python 인터프리터나 NumPy/SciPy를 Wasm에 자동 포함하지 않는다. 계산을 Rust로 구현하고 필요한 수학 함수·라이브러리를 선택한다. 원본의 연산 순서, 예외, NaN/무한대, 정밀도와 경계값을 확인한다. 정규 CDF 등의 대체 구현에는 출처·버전·방법·입력 범위·절대/상대 허용 오차를 먼저 정하고 `verification.md`에 실제 오차와 함께 기록한다. 기대값이나 허용 오차를 실패 결과에 맞춰 몰래 변경하지 않는다. Rust 의존성은 버전/lock과 재현 가능한 공급 경로를 보존한다. vendoring 시 라이선스·원본 해시를 보존한다.

원본의 명시적 정책이 우선이다. 원본에 SQL NULL 계약이 없으면 인자 하나라도 NULL일 때 결과 NULL을 먼저 반환한다. 원본 예외 또는 비유한 결과는 기본적으로 명시적 SQL 오류로 대응하되, 정의된 반환 형식·계산 의미를 바꾼다면 적용 전에 확인한다. 유한 결과가 나오는 경계는 원본 계산을 유지한다. 만기·변동성 0의 극한 공식 추가, 음수의 0 보정, 입력 축소도 변경 크기에 관계없이 확인 대상이다. [호환성 차이와 사용자 확인](compatibility-decisions.md)을 적용하며, 코드에서 명확한 인자 수는 자동 선택하고 기존 합의를 다시 묻지 않는다. Rust 라이브러리·ABI 대체만으로 공개 계약이 유지되면 자동 진행한다.

## 실수형 공용 프로필

```bash
python <skill>/scripts/scaffold.py --name my_function --shape f64-scalar \
  --arguments s k t r sigma --output <new-project>
```

생성된 `src/logic.rs`에 원본 계산과 독립 Rust 테스트를 구현한다. manifest의 `arguments`는 원본 순서다. BASIC ABI의 f64와 SQL DOUBLE을 사용한다. `interface.wit`는 내부 인터페이스 기록·검사용이며 BASIC 등록 SQL에는 WIT를 붙이지 않는다. [SingleStore ABI](https://docs.singlestore.com/db/v9.1/reference/code-engine-powered-by-wasm/wasm-application-binary-interfaces-abis/)와 [등록 구문](https://docs.singlestore.com/db/v9.1/reference/code-engine-powered-by-wasm/create-wasm-udfs/)을 근거로 하되 실제 엔진 호환 여부는 별도 검증한다.

`function.json`에는 아래 필드를 추가하고, `cases`의 기대값은 Rust 실행 전에 원본·독립 근거로 정한다.

```json
{
  "comparison": {"absolute": 1e-10, "relative": 1e-12},
  "python_reference": {
    "source": "tests/reference.py",
    "callable": "function_name",
    "packages": ["numpy", "scipy"],
    "extra_cases": "tests/oracle-cases.json"
  }
}
```

허용 오차는 예시이며 함수의 단위·범위에 맞춰 정한다. 비교식은 `abs(actual - expected) <= absolute + relative * abs(expected)`다. NULL은 별도 NULL-safe 비교한다. 추가 기준 사례 파일은 선택 사항이며 `[{"id":"case_name","args":[...]}]` 형태다. JSON 입력·기대값은 유한 숫자 또는 NULL을 쓴다. 예외 사례는 `expected_error` 문자열을 쓴다.

오류 전달에 유한 `error_sentinel`과 `error_message`를 사용할 수 있다. sentinel이 정상 결과와 겹치지 않는지 확인하고 예약 값의 의미를 계약에 명시한다. 원본 결과 범위상 안전한 값이 없으면 이 프로필에 억지로 맞추지 말고 오류 전달 ABI를 확장한다. wrapper는 NULL을 먼저 처리한 뒤 sentinel을 SQL 2242 오류로 바꾼다.

공용 `build.py`는 Rust 테스트·release 컴파일·import/시그니처/메모리 검사 후 Wasmtime에서 실제 f64 Wasm을 실행한다. `verify_numeric.py`는 manifest 기대값 및 가능한 경우 원본 Python 결과를 같은 오차 기준으로 대조한다. 함수별 빌드/DB 실행기를 복제하지 않는다. 원본 의존성은 별도 검증 환경에 설치하고 버전을 기록한다. 원본 로딩이 불가능하면 `python_reference.status=unavailable`, 이유와 대체 근거를 기록하며 Python 동등성을 통과라고 하지 않는다. 원본과 불일치는 빌드 실패다. NULL은 로컬 Wasm으로 검증했다고 하지 않고 SQL wrapper/DB 검증 항목으로 남긴다.

`artifacts/numeric-verification.json`에 실제 비교 결과를 남긴다. Base64·등록/정상/오류 SQL 생성, status 판정, 기존에 허용된 DB 설정을 이용한 CREATE-only 실행은 공용 도구를 사용한다. DB에 접속하지 못해도 로컬에서 가능한 생성·검증을 완료하고 연결 시도 실패와 미실행을 구분한다. 최종 출력 구조와 실행 환경 표를 유지하고 상세 근거는 `verification.md`에 남긴다.

## 배포판에서 최소 입력 평가

배포된 저장소의 Skill을 read-only로 사용하고 별도의 새 작업 디렉터리에서 평가한다. 평가 입력은 원본 Python 코드와 “이걸 SingleStore Wasm으로 변환해줘”뿐이다. ABI·타입·대체 구현·오차·검증 설계는 에이전트가 수행한다. 새 출력 디렉터리에 Rust를 작성하며 미리 작성된 동일 함수 구현을 복사한 테스트를 Python 분석·이식 평가로 보고하지 않는다.

패키지 해시, 최소 요청, 원본 해시, 사용한 도구 경로, 생성 소스, 정상·경계·오류 비교, DB 등록·실행 여부를 보존한다. 패키지의 자동 회귀 테스트와 에이전트가 원본에서 수행한 이식 평가를 구분한다. 원본 실행에 필요한 NumPy/SciPy 등의 패키지는 입력 코드와 참조 버전에 따라 작업용 가상환경에 별도로 준비하고 실제 설치 버전을 기록한다. 이들은 Wasm 런타임 의존성이 아니다. 준비할 수 없으면 원본 실행 비교를 미검증으로 보고한다. 새 OS 검증, 독립 에이전트 평가, 부하 테스트를 실제로 하지 않았다면 수행했다고 표현하지 않는다.
