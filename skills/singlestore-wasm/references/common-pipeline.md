# 공통 실행기와 배포 검증

## 집계 프로필

공통 `build.py` / `db_verify.py`는 scalar 세 shape 및 `kind: handle-udaf`, `schema_version: 1`을 지원한다. 새 집계 함수마다 Python 빌드·DB 실행기를 만들 필요는 없다. 알고리즘, 상태 메모리 소유권, 직렬화와 병합은 함수의 Rust 구현에 남는다. 명시적 TEXT/JSON 조건 배열은 json-array-udaf starter를 사용한다. 이 프로필 밖의 타입이나 새로운 ABI는 별도 확장·검증이 필요하다.

집계 manifest 필드:

- `argument_types`: `s64`, `u64`, `s32`, `u32`, `f64`, 명시적 input_contracts를 갖는 `string` 목록. 입력은 NOT NULL. NULL 행의 전처리 의미는 함수 계약에 명시한다.
- `aggregates`: SQL 이름 suffix → `returns`, `callbacks`. 반환 타입은 위 숫자 타입, `option-s64`, `bytes`, 명시적 반환 계약을 갖는 `string`. 숫자 외 반환에는 legacy Canonical 반환 영역이 필요하다.
- `callbacks`: `initialize`, `iterate`, `merge`, `terminate`, `serialize`, `deserialize` → WIT export 이름. `copymerge`, `clone`, `destroy`는 선택한 경우 셋 모두 지정한다. WIT의 하이픈 이름을 SQL의 밑줄 이름에 대응시킨다.
- `cases`: `id`, `rows`(행별 모든 인자), `expected` 또는 `expected_error: {code, contains}`. `variant`는 aggregate suffix. 빈 rows도 FROM이 있는 빈 입력 SQL로 생성한다. DOUBLE은 선택적 절대 `tolerance`, bytes 기대값은 `{hex: "..."}`.
- `fixtures`: 선언형 테이블 열·shard key·행과 그룹별 기대값. `group`, `cube`, `rollup` 지원. 분산 실행 계획도 기록한다.
- `build`: 메모리·스택 크기. `local_verify`: 선택적인 프로젝트 내 Python 검증기. 실제 Wasm 경로를 받고 `{"status":"passed", ...}` JSON을 반환해야 한다. 빌드/DB 실행기 전체를 대체하지 않는다.

작은 독립 예제는 개발 저장소의 `development/tests/fixtures/handle_sum/function.json`이다. sum은 다른 export 이름과 인자 수, 필수 콜백만으로 공통 실행기를 검사한다. 지원 타입 전체가 각각 DB 검증되었다는 뜻은 아니다.

등록·검증 SQL은 Python 객체 목록으로 생성한 뒤, 제공할 SQL 파일을 다시 읽어 실행한다. DELIMITER와 인용문을 인식하는 sql_files.py를 사용하며 단순 세미콜론 분리는 금지한다. validate.sql은 실제값·기대값·passed를 모두 검사하고 validate-errors.sql은 지정 코드와 메시지 조각이 모두 일치해야 한다. ERROR 1064는 항상 검증 실패이며 첫 실패에서 중단한다. 보고서 sql_files에 파일별 실행 상태와 SHA-256을 기록한다. 파일 실행 증거가 없으면 DB 검증 성공으로 표시하지 않는다. 문자열 값은 공통 literal/string_literal의 UTF-8 X'hex' 표현을 사용하며 _utf8mb4 X'hex'는 SingleStore 9.1.1에서 사용할 수 없다. DB별 실제 이름과 SQL은 `artifacts/runs/<name>/sql-plan.json` 및 같은 디렉터리의 SQL에 남는다. 빌드 시의 `artifacts/register.sql`은 DB 검증 과정에서 덮어쓰지 않는다.

## 완료 상태와 산출물

`status.py`의 JSON `state`:

| 상태 | 의미 | 산출물 묶음 |
|---|---|---|
| `not_run` | 새 프로젝트, 빌드·검증 미실행 | 차단 |
| `local_passed_db_unverified` | Rust 테스트·실제 빌드·Base64·해시 통과, 이 빌드의 DB 성공 증거 없음 | DB 미검증 표시로 허용 |
| `db_passed` | 동일 소스·도구·산출물의 등록과 모든 기대 사례 통과 | 허용 |
| `db_failed` | 같은 빌드의 DB 검증 실패/불완전 | 차단 |
| `build_failed_or_stale` | 빌드 실패, 파일 변경, 증거 누락 | 차단 |

`--require-db`는 로컬 성공만으로 내보내지 않는다. `--bundle`은 검사한 파일만 ZIP에 넣고 기존 ZIP을 성공 시에만 교체한다. 기존 ZIP이 남아 있다는 사실은 이번 실행의 성공을 뜻하지 않는다. 실패 시 종료 코드와 보고서를 확인한다. 해시는 변경 탐지용이며 신뢰할 수 없는 작성자를 인증하는 서명은 아니다.

## 배포와 검증 범위

이 Skill은 제품 저장소의 `skills/singlestore-wasm/`에서 배포한다. 저장소 공통 Manifest와 검증 절차를 사용하며 Skill 자체의 ZIP 배포 도구는 포함하지 않는다. 사용 checkout은 read-only로 유지한다.

외부 개발 자료의 tests·fixture는 이 Skill에 포함되지 않는다. 해당 경로는 자료를 별도로 제공한 경우에만 사용할 수 있으며, 기본 생성 workflow의 전제 조건이 아니다. 저장소 형식 검사·도구 로딩 검사와 실제 함수 빌드·DB 호출 검증을 구분한다. 실제 실행하지 않은 검증은 성공으로 보고하지 않는다.

사용자가 생성한 함수의 산출물은 위 `status.py --bundle`로 묶을 수 있다. 결과물 ZIP과 Skill 배포는 별개다.

수동 검증용 `validate.sql`은 scalar/HANDLE 모두 `actual`, `expected`, `passed`를 출력한다. NULL은 NULL-safe 비교, 집계 DOUBLE은 계약의 절대 오차, f64 scalar는 절대+상대 오차를 적용한다. Python 코드 입력과 원본 비교는 [Python 이식 절차](python-porting.md)를 따른다. `validate-errors.sql`은 사례마다 기대 오류 코드와 메시지 조각을 주석으로 남기며, 오류 사례가 없는 경우 이를 명시한다. 최종 답변의 SQL 링크 3개는 같은 등록 이름의 파일 묶음이어야 한다. 분산 fixture 검증은 별도로 `sql-plan.json`에 기록되어 공통 DB 실행기가 수행한다.

반환 계약과 정확한 SQL snapshot 일치 검사는 [return-contracts.md](return-contracts.md)를 따른다. DB 이름/함수명은 빌드에서 확정하고 runner에서 바꾸지 않는다.

JSON 배열 조건용 TEXT 입력은 [JSON 조건 배열](json-condition-array.md)을 따른다. 숫자 고정 인자 프로필은 그대로 지원하며 새 input_contracts/WIT/SQL/ITERATE lowering을 함께 검사한다.
