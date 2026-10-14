# 환경과 수동 재현

Ubuntu에서 Python 3.12, Rustup과 Rust 1.85.0, wasm32-unknown-unknown을 준비한다. Rust profile minimal이면 rustc/Cargo/bundled rust-lld로 이 프로젝트를 빌드할 수 있다. 별도 clang, cargo-wasi, wit-bindgen CLI, wasm-tools는 필요하지 않다.

```bash
rustup toolchain install 1.85.0 --profile minimal
rustup target add wasm32-unknown-unknown --toolchain 1.85.0
python3 -m venv .venv
.venv/bin/pip install -r <skill>/scripts/requirements.txt
```

위 명령은 read-only Skill checkout 밖의 쓰기 가능한 작업 디렉터리에서 실행한다. `.venv`, 생성 프로젝트, `.local` 설정과 산출물은 그 작업 디렉터리에 둔다. `<skill>`은 설치된 Skill의 실제 절대경로이며 사용자의 기존 Rustup/PATH를 사용한다. Python 원본 실행에 필요한 추가 패키지는 원본 코드와 버전을 확인하여 작업용 가상환경에 별도로 준비한다.

DB는 제공됐을 때만 연결한다. 필요한 권한은 허용 DB의 함수 생성·호출·메타데이터 조회이며 cleanup 선택 시 해당 생성 객체 삭제 권한도 필요하다. root를 요구하지 않는다. 최소 권한 계정으로의 동작은 별도 검증한다.

로컬 설정 예시(실제 비밀번호를 문서에 적지 않는다):

```ini
[client]
host = YOUR_DB_HOST
port = 3306
user = YOUR_ALLOWED_USER
password = SET_ONLY_IN_LOCAL_FILE
database = t
```

디렉터리 mode 700, 파일 mode 600으로 저장하고 `.gitignore`에서 제외한다. ConfigParser interpolation은 꺼져 있어 비밀번호의 `%`도 그대로 읽는다. 명령행에는 `--config` 경로만 넘긴다.

`function.json` 스키마: name/shape/null_policy/cases 필수, 선택 error_sentinel/error_message/max_codepoints. name은 lowercase identifier 36자 이내. case의 args는 shape의 인자 수와 일치해야 한다. expected 정수/NULL 또는 expected_error 메시지를 지정한다. f64-scalar는 실수 기대값, 인자 목록, 절대·상대 오차 및 선택적 Python 원본 비교를 지원하며 [Python 이식 절차](python-porting.md)를 따른다. repeat 객체는 Python에서 펼쳐 UTF-8 hex SQL 리터럴로 만든다. 검증 기대값은 클라이언트에서 전개한 UTF-8 hex 리터럴로 생성한다. MySQL 표현식의 호환성을 가정하지 말고 대상 엔진에서 확인한다.

새 요청에는 [호환성 결정 기록](compatibility-decisions.md)의 `compatibility`도 포함한다. 조건 개수와 공개 계약을 먼저 확정하고 선택한 함수만 생성한다. 이 기록은 build/SQL/DB 공통 검사 및 소스 해시에 포함되므로 선택을 바꾼 뒤 이전 SQL을 재사용하지 않는다.

빌드 후:

- `artifacts/build.log`: 실행 명령, Rust 테스트·컴파일 출력
- `build.json`: 버전·flags·hash·메모리·export 목록 및 로컬 단계 결과
- `module.wasm`, `module.wasm.b64`: 실제 바이너리와 Base64
- `register.sql`: core + public wrapper, MySQL CLI DELIMITER 포함, CREATE-only
- `validate.sql`: 정수/NULL 비교, 모든 passed가 1이어야 함
- `validate-errors.sql`: 각 문장이 문서화한 사용자 오류를 내야 함
- `runs/<run_id>/preflight.sql`: DB runner 실행 시 생성되는 서버·설정·객체 조회
- `runs/<run_id>/`: DB runner가 기록한 실행 당시 SQL snapshot과 해당 실행의 `db-results.json`
- `db-results-<name>.json`, `db-results-latest.json`: 실제 등록·호출 결과

`run_id`는 보고서에 기록되는 실행별 식별자이며 SQL 함수명과 별개다. 함수명별 결과 파일과 latest 파일은 최신 시도를 가리키고, 이전 시도의 기록은 각 실행 폴더에 보존한다. 연결 실패 후 같은 빌드로 재시도할 수 있으며 기존 DB 객체 충돌 검사는 그대로 적용한다. 상태 확인과 ZIP 생성은 보고서의 `run_id`로 SQL snapshot을 찾고, 이 필드가 없는 과거 보고서는 기존 `runs/<함수명>/` 경로를 사용한다. 다른 지침의 `runs/<name>/`은 새 보고서에서는 이 실행별 폴더를 뜻한다.

PyMySQL runner는 DELIMITER가 필요 없는 개별 statement로 실행한다. SQL 파일은 MySQL 호환 CLI에서 직접 재현 가능하다. 이미 등록된 이름에 register.sql을 다시 실행하면 실패하도록 설계했다. 새 이름이 필요하면 `build.py`로 재생성한다. `db_verify.py`는 빌드에서 확정한 이름을 사용한다. 기존 이름의 validate SQL은 바로 실행할 수 있다.

DB 실패 시 report의 failure.stage와 error를 확인한다. raw module/memory/packet 제한이 원인이면 크기를 줄이거나 허용 범위의 함수 GROW TO만 검토한다. 전역 설정을 자동 변경하지 않는다. Rust 타깃 변경으로 해결했다고 가정하지 말고 새 모듈을 실제로 등록한다.

현재 scalar 오류 프로필은 ER_USER_RAISE(2242)와 설정된 메시지를 함께 검사한다. 다른 엔진에서 코드가 달라지면 실제 오류를 조사한 뒤 검증 정책을 갱신하며, 일반 SQL 오류를 성공으로 간주하지 않는다.

HANDLE 집계, 프로그램의 완료 판정과 산출물 ZIP 검증은 [common-pipeline.md](common-pipeline.md)를 따른다.
