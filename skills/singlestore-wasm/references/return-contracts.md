# 반환 계약, 마이그레이션, 검증 근거

WIT의 `string`에는 SQL TEXT/LONGTEXT, 문자 집합 또는 collation 정보가 없다. `return_contracts.py`는 정확한 `(서버 버전, 함수 종류, ABI 프로필)`로 정책을 선택한다. 알 수 없는 조합은 미검증이며 일반 빌드/등록을 차단한다. TEXT를 모든 문자열 함수의 기본값으로 선택하지 않는다.

retention의 JSON 직렬화/TEXT 반환은 [사용자 지정 반환 기본 정책](json-condition-array.md#retention-반환-기본-정책)을 적용하므로 다시 묻지 않는다. 다섯 반환 계약 필드는 그대로 명시하며 정책·WIT·SQL·Wasm 검사와 실제 실행 검증을 생략하지 않는다.

## Manifest

HANDLE UDAF는 `aggregates.<suffix>.returns`, scalar는 최상위 `returns`에 다섯 필드를 선언한다.

```json
{"abi":"string","sql_type":"TEXT","charset":"utf8mb4","collation":"utf8mb4_bin","nullable":false}
```

이 객체는 SQL 선택을 명시한 계약이다. 누락된 문자열 필드를 채우지 않으며 bare `"string"`은 사용자 확인 대상이다. 사용자가 이미 선택했다면 다시 묻지 않는다. `sql_type: LONGTEXT`를 TEXT로 치환하지 않고 9.1.1 HANDLE 정책 위반으로 중단한다. 다른 버전/ABI에서 사용하려면 별도 증거와 프로필이 필요하다. charset/collation이 없는 숫자 계약도 해당 필드에 명시적으로 `null`을 쓴다.

기존 schema_version 1은 유지한다. 구형 숫자 `s64/u64/s32/u32/f64`는 기존 BIGINT/BIGINT UNSIGNED/INT/INT UNSIGNED/DOUBLE NOT NULL로, `bytes`는 LONGBLOB NOT NULL, `option-s64`는 BIGINT NULL로 해석한다. 기존 scalar shape는 s64/BIGINT 또는 f64/DOUBLE의 public wrapper NULL 계약으로 해석하며 core는 NOT NULL이다. 이 호환 규칙과 적용 여부는 `artifacts/return-contracts.json`에 기록한다. 새 scalar scaffold는 명시적 반환 객체를 쓴다.

## 코드 흐름

1. `common.manifest` → `aggregate.validate` / `return_contracts.resolve`: 단일 반환 계약을 해석하고 버전·종류·ABI 정책을 검사한다.
2. `build.py` → `check_project`: 컴파일 전에 legacy flat WIT의 별칭·모든 callback 인자/반환 타입을 manifest와 비교한다.
3. 컴파일 후 실제 Wasm export 인자/반환 시그니처를 WIT lowering 및 기존 ABI 검사와 비교한다. 바이너리 생성 전에 실제 export를 검사했다고 주장하지 않는다.
4. `aggregate.registrations`는 계약의 `sql_type/charset/collation/nullable`에서 RETURNS를 만든다. `check_sql`은 생성 결과와 계약을 독립 비교한다. scalar wrapper/BASIC core도 검사한다. Canonical scalar core는 WIT 기반의 서버 추론 타입이므로 SQL에 없는 RETURNS 절을 검사했다고 쓰지 않는다.
5. `db_verify`는 같은 빌드 이름의 SQL 3개를 바이트 그대로 snapshot에 복사한다. 다른 `--name`/DB는 재빌드를 요구한다. SQL 파일 SHA-256, 실제 파일 내용, 체크된 계획을 비교하고 이후 DB에 연결/등록한다.
6. `status.bundle`은 ZIP을 다시 열어 모든 포함 artifact 해시를 빌드/프로젝트와 비교한다. `status.assess`는 DB 성공 판정 때 원본 SQL과 snapshot 바이트도 다시 확인한다.

정적 결과는 WIT/manifest/Wasm/SQL 일치 및 파일/ZIP 동일성만 의미한다. `db_registration: not_run`은 로컬 빌드 성공으로 갱신하지 않는다. DB 성공 시 버전, CREATE 결과, SHOW CREATE 원문, 실제 SELECT 비교 결과를 저장한다. NULL/빈 입력은 실제 사례가 있을 때만 통과로 표시한다. 분산 fixture 결과와 EXPLAIN은 기록하지만 callback을 직접 계측하지 않은 MERGE/SERIALIZE/DESERIALIZE 경로는 미검증으로 남긴다.

TVF 및 문자열 scalar UDF, nullable string, 다른 문자열 charset/collation, modern component ABI는 현재 지원 프로필이 아니다. 잘못된 HANDLE 규칙을 적용하지 않고 별도 프로필 구현·검증을 요구한다. 저수준 포인터/길이 반환의 메모리 소유권은 타입 검사로 보장할 수 없으며 실제 DB 호출이 필요하다.

[지원 프로필](return-type-policy-9.1.1.json)은 공통 도구가 허용하는 정적 계약이다. 과거 실행의 오류·해시·DB 이름은 개발 기록에 분리했다. 다른 환경의 확정 동작으로 확대하지 않으며 새 프로젝트의 등록·호출은 별도 실행으로 판정한다.

공식 문서: [CREATE AGGREGATE](https://docs.singlestore.com/db/v9.1/reference/sql-reference/procedural-sql-reference/create-aggregate/), [SHOW CREATE AGGREGATE](https://docs.singlestore.com/db/v9.1/reference/sql-reference/procedural-sql-reference/show-create-aggregate/). 문서 버전과 실제 패치 버전을 구분한다.
