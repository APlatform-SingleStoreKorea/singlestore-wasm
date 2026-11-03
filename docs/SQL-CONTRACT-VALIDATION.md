# 공개 SQL 계약 개선과 검증 범위

이 변경은 DB 함수의 공개 SQL 계약과 내부 C/ABI 인자를 분리하는 Skill 및 생성·검증 경로 개선이다. 특정 DB 함수의 완성된 이식 라이브러리를 배포하는 작업은 아니다.

## 적용 내용

- 지정 버전 공식 SQL 문서를 계약의 기준으로 삼고, 소스의 SQL 등록/진입 경로에서 내부 인자의 구성과 기본값을 확인한다.
- 과거 함수별 승인, 고정 비용·길이·빈 입력·반환 정책을 공통 지침에서 제거했다. 개발 자료 보관 위치 안내 문장만 삭제했으며 실제 개발 자료·라이선스 파일은 삭제하지 않았다.
- 원본 호출 유지 가능성을 제품 버전·기능 설정 기준으로 확인한 뒤 필요한 경우 JSON으로 대체한다. 반복 조건 배열화는 고정 인자의 의미·순서를 유지한다.
- version 1 public_contract는 원본/대상 인자, JSON 위치와 길이, 내부 매핑, 복합 값 표현, 계약 차이를 구분한다. 신규 typed 경로는 미합의 차이·잘못된 매핑·인자 순서 변경·추가 내부 인자 노출을 정적으로 거부한다. 기록의 사실성은 공식 자료와 구현 검토로 확인해야 한다.
- typed-scalar와 typed-udaf는 계약에서 WIT/ABI/SQL 인자를 생성한다. 입력 계약은 컴파일 소스에 포함하고 manifest와 다르면 빌드를 거부한다.
- 일반 JSON은 고정 버전 serde_json을 사용한다. 기존 조건 배열 파서·구형 manifest·기존 생성물은 자동 변경하지 않는다.

## PostgreSQL 검증 예시의 근거

기준: PostgreSQL 18.0, `REL_18_0`. [공식 SQL 문서](https://www.postgresql.org/docs/18/fuzzystrmatch.html), [해당 릴리스 SQL 진입 소스](https://github.com/postgres/postgres/blob/REL_18_0/contrib/fuzzystrmatch/fuzzystrmatch.c).

공개 시그니처는 `levenshtein(source text, target text) → integer` 및 `levenshtein(source text, target text, ins_cost integer, del_cost integer, sub_cost integer) → integer`다. SQL 진입 함수는 내부 trusted에 false를 전달하며 두 인자형의 비용은 각각 1이다. 메이저 버전 웹 문서는 갱신 가능하므로 정확한 릴리스 근거와 함께 확인해야 한다.

이 사례는 공개 매핑의 회귀 검사에만 사용했다. 이번 검증은 PostgreSQL 서버의 SQL 실행 또는 Levenshtein 계산 구현의 동등성 검증이 아니다. 공통 생성 코드에 해당 함수 이름의 분기는 없다.

## 호출 대응 예시

아래 SQL은 원본 형태 유지가 어렵다고 확인한 환경에서 사용할 **대응 설명 예시**이며 등록·실행 결과가 아니다. 구현 가능한 환경에서는 원본의 고정 인자를 우선 유지한다.

```sql
-- 원본 공개 호출
SELECT levenshtein('abc', 'axc');
SELECT levenshtein('abc', 'axc', 1, 2, 3);
-- JSON 대체 인터페이스
SELECT ported_distance(JSON_BUILD_ARRAY('abc', 'axc'));
SELECT ported_distance(JSON_BUILD_ARRAY('abc', 'axc', 1, 2, 3));
```

위 예시의 배열 길이는 {2,5}다. 위치 0·1은 source/target 문자열, 2·3·4는 삽입/삭제/치환 비용이다. 길이 2에서만 생략된 비용을 1로 구성하고 명시적 null과 구분한다. trusted·포인터·바이트 길이는 배열에 넣지 않는다. SQL NULL 및 원소 null의 원본 SQL 대응은 원본 등록 정의·실행으로 확인하여 계산 로직에 반영해야 하며, 단순 JSON 파싱 성공으로 NULL 동등성을 주장하지 않는다.

실제 smoke fixture는 별도의 합성 함수다. `[label, count]` 또는 `[label, count, x, y, z]`에서 문자열 길이와 정수를 더한다. 길이 2의 x/y/z는 각각 1, 길이 5는 전달값을 사용한다. label은 non-null 문자열, 숫자는 non-null signed 32-bit 정수다. 길이 3·4, null 원소, 잘못된 타입/범위/JSON은 오류다. SQL NULL 인자는 wrapper에서 NULL 전파하도록 생성되지만 해당 SQL 실행은 미검증이다.

## 검사와 실행

- `tests/test_public_contract.py`: 고정 순서, 내부 인자 비노출, 원본/대상/배열 arity 분리, 허용 길이 집합, 타입·범위, 미합의 차이 거부, 구형 manifest, 재생성 필요 검출, SQL 인자 변조 거부, PostgreSQL 매핑 예시.
- `tests/smoke_public_contract.py`: 외부 디렉터리에 혼합 scalar, JSON 2/5 호출 형태, 중첩 JSON, 혼합 HANDLE, 구형 정수 scalar를 생성하여 실제 Wasm 빌드.
- typed scalar: Wasmtime으로 정상·오류 사례 실행. 쉼표/따옴표 문자열, 음수, 실수, 중첩 object/array, 2^53보다 큰 정확한 정수, 명시적 null, 범위·입력 크기 초과 포함.
- HANDLE: 고정 정수와 반복 boolean 배열의 혼합 전달, merge/copymerge/clone/destroy, serialize/deserialize, 빈 그룹과 잘못된 반복 배열을 Wasmtime으로 실행. 증거는 프로젝트 local_verify로 빌드에 연결한다.
- WIT/manifest/Wasm export/등록 SQL의 정적 일치 검사와 Base64 왕복, 해시 검사.

원본 DB와 SingleStore의 접속 정보가 이번 작업에 제공되지 않아 서버 비교와 등록·호출은 실행하지 않았다. 합성 fixture의 기대값은 테스트 정의에서 미리 지정했으며 구현 결과로 변경하지 않았다.

## 지원 범위와 제한

typed scalar는 string/s32/s64/f64 고정 입력, 일반 JSON string 입력, BIGINT NULL 결과와 NULL 전파를 지원한다. i64::MIN은 오류 sentinel이며 원본 정상 결과에 이 값이 필요하면 다른 오류 경로를 구현해야 한다. 현재 오류는 invalid_input으로 매핑하므로 원본 오류 코드·메시지 동등성을 주장하지 않는다. typed HANDLE은 NOT NULL 입력과 기존 반환 프로필을 사용한다. 다른 계약을 템플릿에 맞춰 의미 변경하지 않는다.

JSON integer는 signed 64-bit를 정확히 처리하고 number는 f64 범위다. Decimal·시간·더 큰 정수는 명시적 표현 및 추가 검증이 필요하다. 중첩 JSON은 명시적 JSON 문자열 입력으로 검증했으며 중첩 JSON_BUILD_ARRAY SQL 생성까지 검증했다고 하지 않는다. 같은 길이의 여러 타입 형태는 유일하게 일치할 때만 선택하고 모호하면 오류다. 원본 SQL의 타입 변환·collation·오류 우선순위는 DB 실행 없이는 미검증이다.

일반 JSON 의존성은 serde_json 1.0.140으로 고정하며 전이 의존성은 생성 프로젝트의 Cargo.lock으로 고정한다. 기존 프로젝트는 덮어쓰지 않으며 전환 시 새 디렉터리에서 재생성·재검증한다.

## 실행 결과

| 항목 | 상태 |
|---|---|
| 저장소 unittest | 18개 통과 |
| manifest 재생성 | 완료 |
| 저장소 validate_skills | 통과 |
| git diff --check | 통과 |
| 실제 Wasm 빌드 | 신규 경로 4개와 구형 scalar 1개 통과 |
| 신규 scalar Wasmtime 실행 | 3개 프로젝트의 정상·오류 사례 통과 |
| 혼합 HANDLE Wasmtime 실행 | 입력·병합·복제·직렬화·빈 입력·오류 사례 통과 |
| ABI/WIT/Wasm/SQL 정적 계약 | 통과 |
| 원본 DB SQL 비교 | 미실행·미검증 |
| SingleStore 등록·호출 | 미실행·미검증 |

추가로 실행한 범용 skill-creator quick_validate는 기존 frontmatter의 author/version을 허용하지 않아 실패했다. 저장소 AUTHORING 규격이 이 필드를 명시하므로 제거하지 않았으며 저장소 전용 검증기는 통과했다. 이 검사는 Wasm 또는 공개 계약 실행 검증과 별개다.
