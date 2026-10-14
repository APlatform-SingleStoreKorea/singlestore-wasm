# 적용 가능성 확인표

공식 기준: [Code Engine](https://docs.singlestore.com/db/v9.1/reference/code-engine-powered-by-wasm/), [Create Wasm UDFs](https://docs.singlestore.com/db/v9.1/reference/code-engine-powered-by-wasm/create-wasm-udfs/), [ABIs](https://docs.singlestore.com/db/v9.1/reference/code-engine-powered-by-wasm/wasm-application-binary-interfaces-abis/), [Configure Wasm](https://docs.singlestore.com/db/v9.1/reference/code-engine-powered-by-wasm/configure-wasm/).

매 요청마다 다음을 기록한다.

분석 후 생성에 들어가기 전에 [호환성 차이와 사용자 확인](compatibility-decisions.md)을 적용한다. 명확한 인자 수·기존 합의는 재질문하지 않고, 호출 방식만의 변경은 자동 진행 정책에 따라 기록하고 확인 없이 진행한다. 공개 함수 수·반환 형식·계산 의미의 미합의 변경은 사용자 답변 후 확정한다. 범위 전체 지원과 의미 변경 동의는 별개다.

| 영역 | 확인할 내용 |
|---|---|
| 의미 | scalar/여러 행 상태/rowset 중 무엇인가, 입력·결과 타입, NULL, 빈 값, 오류 |
| Unicode·숫자 | 코드 포인트/바이트/grapheme, 정규화, 정밀도, overflow, NaN |
| ABI | Basic은 숫자 위주, 문자열은 Canonical. 현재의 수동 ABI 지원 shape 확인 |
| 의존성 | host import, 파일·네트워크·OS·threads가 필요한가. 필요 기능을 제공하지 못하면 불가 또는 설계 변경 조건 |
| 자원 | DP 셀 수 등 시간 예산, 입력·상태·출력 메모리, raw/compiled 모듈과 packet 크기 |
| 서버 | 실제 엔진 patch, enable_wasm 및 한도 조회. 전역 변경은 별도 사용자 범위 필요 |
| 증거 | 실제 산출물 hash와 등록·호출 결과. 문서만 확인한 것은 미확인 |

조건부 가능은 설계가 맞지만 아직 DB 실행 검증 또는 필요한 ABI 구현이 남은 상태다. 가능은 **검증된 함수·빌드·서버 조합**에 한정한다. 다른 패치/컴파일러/함수 타입으로 일반화하지 않는다.

기본 대상은 SingleStore 9.1.1이다. 참조 함수의 공식 문서·필요한 원본 소스에서 버전, 입력·출력, 옵션과 기본값을 확인하고 출처를 기록한다. DB가 없으면 문서에 근거한 판단과 실제 등록·호출 미검증을 구분한다.

현재 scaffold는 scalar 세 shape(string-pair-i64, i64-unary, f64-scalar)와 json-array-udaf를 제공하며, 공통 빌드·DB 실행기는 숫자 및 명시적 TEXT 입력 HANDLE UDAF를 지원한다. 템플릿이 없다는 이유로 제품에서 구현 불가능하다고 판정하지 않는다. UDAF·TVF가 제품에서 제공된다는 사실과 이 스킬이 그 생성기를 제공한다는 주장은 다르다. 필요한 ABI·템플릿·빌드/검증 경로의 추가 구현 가능성을 검토하고 가능하면 구현·컴파일·Base64 생성까지 진행한다. 이벤트 집계는 상태 직렬화·병합, 순서/동일 timestamp, 파티션, 종료·NULL 의미를 확인한 다음 구현한다. 원본 의미를 보존할 수 없는 설계 변경은 임의로 적용하지 않는다.

레벤슈타인 계약: Unicode scalar 기준 비용 1, 정규화 없음, NULL 우선, 입력당 최대 4096. 이 한도는 프로젝트 정책이다. 시간 O(mn), 핵심 추가 메모리 O(min(m,n)); ABI 입력 버퍼도 고려한다. 4096² 셀의 단일 테스트는 대규모 동시 처리 SLA를 입증하지 않는다.
