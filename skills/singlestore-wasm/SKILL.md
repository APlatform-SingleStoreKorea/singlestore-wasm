---
name: singlestore-wasm
description: Use when creating SingleStore Wasm functions. Implements function descriptions or Python/Rust code and verifies Wasm build artifacts and registration SQL.
version: 1.0.0
author: Consulting Team
license: Proprietary
metadata:
  org:
    tags: [singlestore, wasm, rust, udf, udaf]
    required_capabilities: [shell]
    optional_capabilities: [network]
---

# SingleStore Wasm 함수 생성

## Overview

사용자 요구를 **SingleStore에 등록·실행 가능한 함수**로 구현한다. 입력은 ① 코드와 “이걸 SingleStore Wasm으로 변환해줘” 또는 ② 함수 이름·동작 설명과 구현 요청이다. Python 코드 분석·Rust 이식과 기존 Rust 입력을 지원한다. 다른 언어는 원본 의미와 이식 가능성을 별도로 판단하며 일괄 지원을 가정하지 않는다. 사용자가 ABI·Rust 타입·라이브러리 대체·검증 방식을 지정할 필요는 없다.

Python 입력에서는 [Python 이식 절차](references/python-porting.md)를 읽는다. Codex가 소스와 의존성을 분석해 Rust로 구현하는 흐름이며 별도의 범용 Python→Rust 자동 변환기는 만들지 않는다. 원본 실행이 가능하면 독립 기준으로 비교하고, 실행 불가 시 이유와 대체 검증 근거를 기록한다. 함수 이름·설명 입력은 기존 판단·구현 절차를 따른다.

### 기본 완료 범위

사용자가 구현할 함수만 간단히 요청해도 스킬이 선택되면 **① 적용 가능성 판단 → ② Rust와 연결 코드 구현·실제 Wasm 컴파일 → ③ 실제 바이너리의 Base64 변환·등록 SQL 제공**을 기본으로 수행한다. 사용자가 명시적으로 검토만 요청하는 등 범위를 제한한 경우에는 그 범위를 따른다.

기본 대상은 **SingleStore 9.1.1**이다. 다른 버전을 지정하면 해당 버전을 기준으로 판단한다. 구현 가능한 경로가 있으면 적합성 설명이나 계획만 제시하고 멈추지 말고 빌드와 산출물 생성까지 이어간다. DB 접속 정보가 없어도 로컬 구현·빌드·인코딩은 진행하고 DB 등록·호출은 미검증으로 표시한다. 컴파일 성공과 실제 DB 호환 성공은 구분한다.

먼저 요구사항과 호환성을 분석한다. 코드·SQL 또는 기존 대화에서 인자 개수가 명확하면 해당 범위로 자동 진행한다. 내부 구현 또는 호출 방식만 달라지고 공개 함수 개수·반환 형식·계산 의미가 유지되면 사용자 확인 없이 진행한다. 호출 방식 변경은 [호환성 결정의 자동 진행 정책](references/compatibility-decisions.md#호출-방식-변경의-자동-진행)에 따라 기록하고 최종 사용 예시로 설명한다. 원본 대비 공개 함수 개수·반환 형식·계산 의미를 바꿔야 하면 차이와 구체적인 선택지를 설명하고 답변을 받은 뒤 설계를 확정한다. 전체 지원 요청은 범위 선택이며 반환 형식·계산 의미 변경 동의가 아니다. 이미 합의한 사항은 다시 묻지 않는다.

모든 요청에서 [호환성 차이와 사용자 확인](references/compatibility-decisions.md)을 읽고 분석 → 범위·차이 결정 → 생성 → 등록 순서를 따른다. 답변 전에도 공통 조사·분석은 진행하지만 선택이 필요한 함수의 설계·생성·등록은 확정하지 않는다. 통상적인 내부 구현·출력 경로는 스킬이 정한다. 불가능하거나 차단된 경우에는 근거, 실패 단계, 필요한 정보 또는 환경을 설명한다. 수정 가능한 실패는 해결하고 재시도하되, 실패·부분·이전 산출물을 이번 요청의 정상 결과처럼 제공하지 않는다.

retention을 행별 JSON 조건 배열 하나로 받는 경우, 입력 행이 전혀 없어 조건 수를 알 수 없는 집계의 결과는 기본적으로 `[]`로 한다. 이 빈 입력 정책은 사용자가 지정한 기본값이므로 다시 승인받지 않는다. 다른 빈 입력 결과나 고정 인자 호출을 사용자가 명시하면 그 요구를 우선한다. 세부 적용 범위와 결정 기록은 [JSON 조건 배열](references/json-condition-array.md)을 따른다. retention의 배열 결과는 기본적으로 JSON으로 직렬화하여 `TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL`로 반환한다. 이 반환 정책도 사용자가 지정한 기본값이므로 다시 묻지 않는다. 다른 함수나 사용자가 명시한 다른 반환 계약에는 확대 적용하지 않는다.

## When to Use

- 함수 이름·동작 설명으로 SingleStore용 Wasm 함수와 등록 SQL을 만들 때 사용한다.
- Python 또는 Rust 코드를 SingleStore Wasm으로 이식하고 원본 의미를 비교할 때 사용한다.
- 이 workflow로 만든 함수의 빌드·반환 계약·등록·호출을 검증하거나 실패를 조사할 때 사용한다.

## Do Not Use

- SingleStore 클러스터 설치나 업그레이드에는 사용하지 않는다.
- 기존 SQL의 실행 계획·인덱스·물리 설계를 튜닝하는 요청에는 사용하지 않는다.
- SingleStore와 무관한 브라우저용 Wasm 또는 범용 Python→Rust 자동 변환기 개발에는 사용하지 않는다.
- 알려진 starter가 없다는 이유만으로 구현 불가로 판정하지 않는다. 다른 언어·ABI·함수 형태는 개별 분석과 확장 검증이 필요하다.

## Prerequisites

1. 함수 설명 또는 원본 코드, 입력·반환 계약, 대상 SingleStore 버전을 확인한다. 기본 대상은 9.1.1이며 기존 대화에서 확정된 사항은 다시 묻지 않는다.
2. [환경 설정](references/workflow.md)에 따라 Python 3.12, Rust 1.85.0 및 wasm32-unknown-unknown target과 `scripts/requirements.txt`의 실행 의존성을 준비한다. Python 원본 비교에 필요한 추가 패키지는 입력 코드에 따라 별도로 준비한다.
3. `<skill>`은 이 SKILL.md가 있는 실제 디렉터리다. 사용 checkout은 read-only로 유지하고 가상환경·생성 프로젝트·로그·DB 설정은 저장소 밖의 쓰기 가능한 작업 디렉터리에 둔다. 명령의 상대 출력 경로는 그 작업 디렉터리를 기준으로 한다.
4. DB 접속 정보와 해당 작업 권한은 DB 검증 시에만 필요하다. 외부 로컬 INI 설정을 사용하며 credential 값을 저장소·명령행·로그에 넣지 않는다.

완료 조건: 로컬 작업 범위와 도구 환경이 확인되었다. DB 정보가 없으면 로컬 작업을 계속하고 DB 미검증 상태를 보고한다.

## Procedure

1. **요구사항과 호환성을 분석한다.** [구현 절차](references/implementation.md)의 판단과 계약을 읽는다. 모든 요청에서 [호환성 결정](references/compatibility-decisions.md), [지원 범위](references/compatibility.md)를 확인하고 Python 입력이면 [Python 이식](references/python-porting.md)을 읽는다. 이름·설명 입력은 [원본 비교](references/reference-verification.md)를 따른다.

   완료 조건: 함수별 feasibility.md에 참조 버전·출처, 입력·출력·NULL·옵션·경계 사례, ABI와 외부 의존성, 가능/조건부 가능/불가 근거를 기록했다. 호출 방식만의 변경은 자동 진행 근거를 기록했고, 공개 함수 개수·반환 형식·계산 의미의 변경은 사용자의 선택이 확정되었다.

2. **새 작업 디렉터리에 구현한다.** [구현 절차](references/implementation.md)에 따라 `scripts/scaffold.py`와 `templates/`를 사용하고 Rust 로직·테스트·독립 기대값을 작성한다. 반복 조건 배열이면 [JSON 조건 배열](references/json-condition-array.md), 새 ABI이면 [ABI](references/abi.md), HANDLE 집계이면 [공통 실행기](references/common-pipeline.md)를 읽는다.

   완료 조건: 요청된 의미와 선택된 계약이 소스·function.json·WIT에 반영되었고 과거 승인이나 검증 성공을 상속하지 않았다. 기존 구현을 덮어쓰지 않았다.

3. **반환 계약을 검사하고 빌드한다.** [실행 절차](references/execution.md)와 [반환 계약](references/return-contracts.md)에 따라 `scripts/build.py`를 실행한다. 미구현 starter나 임의 기대값으로 성공 처리하지 않는다.

   완료 조건: 실제 Rust 테스트·Wasm 컴파일, WIT/manifest/export/SQL 계약 검사, Base64 왕복과 SHA-256 검사가 통과하고 등록·정상·오류 검증 SQL이 생성되었다. 원본 실행 비교 여부를 별도로 기록했다.

4. **허용된 경우 DB에서 검증한다.** [실행 절차](references/execution.md)의 DB 실행 규칙에 따라 `scripts/db_verify.py`로 제공 SQL의 snapshot을 등록·호출한다. DB 미제공이면 이 단계만 미실행으로 기록한다.

   완료 조건: 실제 서버·객체·SQL snapshot과 정상/오류 사례 결과를 기록했다. 충돌 시 기존 객체를 교체하지 않았다. 등록과 호출, 분산 callback 검증 범위를 구분했다.

5. **상태와 결과를 전달한다.** `scripts/status.py`로 현재 소스·도구·산출물의 상태를 확인한다. 결과물을 묶을 때만 `--bundle`을 사용한다. [최종 결과 형식](references/output-format.md)을 읽고 [환경 기록](references/validated-environment.md)에 따라 verification.md를 작성한다.

   완료 조건: Wasm·Base64·등록 SQL·정상 검증 SQL·오류 검증 SQL 링크와 실제 검증 범위, 원본 의미 비교·입력/반환 계약·미검증 사유가 보고되었다. 실패·부분·오래된 산출물을 성공 결과로 전달하지 않았다.

## Failure and Rollback

- 실패한 단계와 실제 오류를 기록하고 수정 가능한 원인을 해결한 뒤 재검증한다. 실행하지 않은 복구 명령이나 성공 결과를 만들지 않는다.
- 기존 파일을 덮어쓰지 않고 새 출력 디렉터리를 사용한다. DB 객체 이름이 충돌하면 중단하고 새 이름으로 재빌드한다.
- DB runner는 CREATE-only이며 기존 객체에 OR REPLACE/DROP을 적용하지 않는다. `--cleanup`은 사용자가 정리를 허용한 경우 이번 프로세스가 생성한 객체만 정리한다.
- 전역 DB 설정 변경·서버 재시작·다른 DB 변경은 이 절차에 포함하지 않는다.
- DB 연결 실패와 DB 미실행을 구분한다. 가능한 로컬 작업은 완료하되 컴파일 성공을 실제 DB 호환 성공으로 보고하지 않는다.
- 소스·도구·산출물 해시가 달라지거나 검증이 실패하면 `status.py`의 내보내기 차단을 우회하지 않는다.

## Common Pitfalls

- Python 원본 실행 증거와 AI가 작성한 기대값을 혼동하지 않는다. 실행 불가 시 의미 검증은 미검증으로 보고한다.
- 반복 조건은 기본적으로 JSON 배열 하나로 받지만, 인자마다 의미가 다른 함수에 일괄 적용하지 않는다. 세부 규칙은 구현 절차를 따른다.
- WIT의 string만으로 SQL TEXT/LONGTEXT·charset·collation·nullable을 정하지 않는다. 반환 계약에 각각 명시한다.
- ABI/WIT 또는 템플릿만 바꾸고 기존 빌더가 호환된다고 가정하지 않는다. manifest·시그니처 검사와 검증 경로도 확인한다.
- 이전 요청의 승인·원본 비교·DB 성공을 새 요청에 적용하지 않는다. 함수명이나 DB가 바뀌면 재빌드하고 SQL snapshot을 일치시킨다.
- core/wrapper 이름과 사용자 호출용 이름을 구분한다. 실제 Base64 대신 placeholder를 제공하지 않는다.

## Verification Checklist

- [ ] 함수 범위·대상 버전·원본 계약과 의미 변경에 대한 결정이 명확하다.
- [ ] 기대값은 원본 설명·코드에서 먼저 정했고 원본 실행 비교 여부를 기록했다.
- [ ] 실제 테스트·컴파일·Base64 왕복·반환 계약 검사가 통과했다.
- [ ] DB 등록·호출 결과와 미실행/실패/미검증 범위를 구분했다.
- [ ] 현재 소스·도구·SQL·산출물 해시와 보고서가 일치한다.
- [ ] 최종 결과 형식의 파일 링크와 계약·제약·verification.md를 제공했다.
- [ ] read-only Skill checkout에 환경·산출물·credential을 쓰지 않았다.

## References

- [구현 절차](references/implementation.md): 절차 1~2의 분석, 반복 조건과 starter 사용·확장 규칙.
- [호환성 결정](references/compatibility-decisions.md): 모든 요청의 범위·공개 계약 차이와 사용자 선택.
- [지원 범위](references/compatibility.md): 절차 1의 SingleStore 적합성 판단.
- [Python 이식](references/python-porting.md): Python 입력의 의미 분석·원본 비교.
- [원본 비교](references/reference-verification.md): 이름·설명 입력의 고정 출처와 독립 실행 증거.
- [JSON 조건 배열](references/json-condition-array.md): 반복 조건을 받는 함수의 호출과 빈 입력 정책.
- [ABI](references/abi.md): starter에 없는 타입·형태 또는 연결 코드를 구현할 때.
- [반환 계약](references/return-contracts.md): 반환 타입 생성·변경 및 WIT/SQL/Wasm 검증. 연결된 `references/return-type-policy-9.1.1.json`의 검증 범위를 따른다.
- [환경 설정](references/workflow.md): 사전 환경 준비, 수동 재현과 실패 조사.
- [실행 절차](references/execution.md): 절차 3~4의 빌드·산출물·DB 실행 규칙.
- [공통 실행기](references/common-pipeline.md): 집계 manifest·상태와 결과물 묶음.
- [최종 결과 형식](references/output-format.md): 절차 5에서 읽는 답변 형식과 검증 상태 표시 규칙.
- [환경 기록](references/validated-environment.md): 실제 환경과 검증 근거를 기록할 때.
- `scripts/requirements.txt`: 작업용 가상환경에 설치하는 실행 의존성 목록.
- `scripts/scaffold.py`, `scripts/build.py`, `scripts/db_verify.py`, `scripts/status.py`: 위 절차에서 사용하는 생성·빌드·DB 검증·상태 도구. 나머지 Python 파일은 이 도구의 공통 모듈 또는 참조 문서에서 연결한 보조 검사기다.
- `templates/rust/`, `templates/sql/`, `templates/json-array-udaf/`: scaffold와 공통 실행기가 읽는 소스·SQL·집계 starter. 새 함수의 계산과 계약·기대값은 별도 구현한다.
