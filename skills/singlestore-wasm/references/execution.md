# 반환 계약, 빌드와 DB 검증

## 반환 타입 계약

반환 타입을 생성하거나 변경할 때 [반환 계약과 검증](return-contracts.md)을 따른다. WIT는 SQL TEXT/LONGTEXT 길이 계층, charset, collation을 결정하지 않는다. manifest에 ABI와 SQL 계약을 분리하고 문자열은 사용자가 선택한 sql_type·charset·collation·nullable을 모두 명시한다. bare `returns: "string"`은 자동 변환하지 않고 확인한다. 구형 숫자·바이너리 계약은 문서화된 마이그레이션만 허용한다.

빌드 전 WIT·manifest 검사, 컴파일 후 실제 Wasm export 검사, SQL 생성 후 RETURNS·callback 검사를 각각 통과해야 한다. 서버 버전·UDF/UDAF/TVF·ABI별 미검증 프로필을 다른 프로필의 성공으로 대체하지 않는다. 정적 성공과 DB 등록·SHOW CREATE·호출·분산 callback·NULL/빈 입력 검증을 구분한다. 분산 호출 성공만으로 MERGE 또는 SERIALIZE/DESERIALIZE callback 경로를 직접 확인했다고 쓰지 않는다.

## 빌드와 산출물

[workflow.md](workflow.md)의 환경 설정 후:

```bash
python3 <skill>/scripts/build.py <new-project> --database t
```

Rust 1.85.0, wasm32-unknown-unknown을 고정한 프로필이다. 기존 정수·문자열 프로필은 외부 Rust 크레이트가 없다. Cargo.lock을 보존하고 `--locked --offline`로 테스트·빌드한다. 새 의존성이 필요하면 pin/lock하고 host import와 빌드 재현성을 검토한다. 현재 build.py는 import 없는 순수 함수 프로필만 받는다.

빌더는 `artifacts/`에 실제 Wasm, 도구로 생성한 Base64, 왕복 검증과 SHA-256, Wasm 구조 목록, 빌드 로그, 등록·호출 SQL을 남긴다. 새 형태의 빌드 경로에도 같은 검증·산출물 원칙을 적용한다. **성공적으로 컴파일한 실제 바이너리**를 인코딩하고 디코딩 결과가 원본과 같은지 검사한다. 가상 Base64나 placeholder SQL을 완료 산출물로 제공하지 않는다.

`python3 <skill>/scripts/status.py <new-project>`로 완료 상태를 판정하고, 전달용 ZIP은 `--bundle <output.zip>`으로 만든다. DB 성공이 필요한 경우 `--require-db`를 추가한다. 실패하거나 소스·도구·산출물 해시가 달라진 결과는 내보내지 않는다. [공통 실행 절차](common-pipeline.md)에 상태값과 배포·검증 범위가 있다.

사용자에게 아래 최종 결과 형식으로 `module.wasm`, `module.wasm.b64`, `register.sql`, `validate.sql`, `validate-errors.sql`의 클릭 가능한 파일 링크를 모두 제공한다. Base64 본문은 대화에 출력하지 않는다. DB 실행 전에는 등록용 산출물이 준비된 상태이며, 실제 엔진에서 로드·호출 가능한지는 미검증임을 명시한다. 구조 검사만으로 전체 Wasm validation 또는 SingleStore 호환성을 주장하지 않는다.

## DB 실행

DB 설정이 제공되고 그 DB 작업이 허용된 경우에만 실행한다. 사용자 제공 범위를 따른다. root는 필요 조건이 아니다. 설정은 Git 제외 로컬 INI 파일(mode 600), 비밀번호는 명령행·소스·로그에 넣지 않는다. [workflow.md](workflow.md)에 예시가 있다.

```bash
python3 <skill>/scripts/db_verify.py <new-project> --config <local-db.ini> --database t
```

함수명은 build.py 단계에서 고유하게 확정한다. DB runner는 `artifacts/` SQL 3개를 snapshot으로 그대로 복사해 실행하고 바이트와 SHA-256을 비교한다. 다른 이름이나 DB가 필요하면 해당 설정으로 재빌드한다.

실제 `@@memsql_version`, Wasm 변수, packet 크기와 기존 함수/프로시저/테이블/UDAF를 조회한 뒤 고유 `ssws_...` 이름으로 CREATE만 한다. 충돌 시 중단하고 새 이름을 쓴다. 기존 객체에 OR REPLACE/DROP을 적용하지 않는다. 전역 설정 변경·서버 재시작·다른 DB 변경은 포함하지 않는다. 기본은 생성 객체를 보존한다. `--cleanup`은 이번 프로세스가 생성한 객체만 정리한다.

`artifacts/runs/<name>/`의 실제 등록·검증·preflight SQL 및 문장 목록 snapshot과 JSON 보고서를 확인한다. 연결 실패 시 가능한 로컬 작업을 완료하되 DB 시도 실패와 DB 미실행을 구분한다. 실패는 단계/오류/원인/수정 내용을 비밀정보 없이 기록한다.
