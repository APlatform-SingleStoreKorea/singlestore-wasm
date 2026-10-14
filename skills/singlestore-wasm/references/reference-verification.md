# 원본 출처와 실행 비교

이름·설명 기반 생성의 공통 절차다. 특정 함수나 엔진에 한정하지 않는다.

1. 실제 참조한 공식 문서와 원본 소스를 기록한다. 원본 엔진 버전/소스 커밋을 고정하고 `master` 링크만으로 버전을 대신하지 않는다. 소스 미확보 시 이유를 적는다.
2. 원본 엔진 또는 고정 원본 계산 코드를 실행하는 어댑터를 작성한다. 원본 소스·의존 코드·버전·실행 환경과 어댑터 변경 범위를 보존한다. 독립 실행기로 추출한 계산 코드는 엔진의 타입/NULL 처리까지 검증한 것으로 표현하지 않는다.
3. 구현 결과를 보기 전에 원본 실행으로 기대값을 얻어 `function.json.cases`를 채운다. AI가 새로 작성한 참조 알고리즘이나 상수 반환은 원본 실행의 대체물이 아니다.
4. 공통 빌더는 원본과 Wasm 어댑터를 같은 입력으로 다시 실행하고 결과를 manifest 기대값과 비교한다. SQL 생성·DB 검증도 이 manifest를 사용한다. 실패한 기대값을 Wasm 결과에 맞춰 바꾸지 않는다.
5. 원본 실행 불가 시 `unavailable_reason`을 기록한다. 빌드는 허용하지만 `semantic_verification`은 미검증이다. DB 통과와 출처 확보만으로 이를 통과로 바꾸지 않는다.

## Manifest

`function.json`에 다음 필드를 추가한다. `sources`에는 실제 문서/소스 링크, 각 버전·커밋 및 확보 상태를 기록한다. 없는 링크를 만들어 넣지 않는다.

```json
{
  "reference": {
    "sources": [
      {"kind": "documentation", "url": "https://official.example/docs/function", "version": "fixed-version"},
      {"kind": "source", "url": "https://official.example/source/fixed-commit/function", "commit": "fixed-commit"}
    ],
    "revision": "immutable upstream revision",
    "files": ["scripts/upstream.py", "scripts/wasm_reference.py", "tests/reference/source.cpp"],
    "command": ["python3", "scripts/upstream.py"],
    "wasm_command": ["python3", "scripts/wasm_reference.py"],
    "timeout_seconds": 120
  }
}
```

명령은 shell 문자열이 아닌 argv다. 사전 검토한 코드만 실행하며 외부 엔진 사용은 기존 접속·실행 권한을 따른다. 실행 불가 시 command를 생략하고 이유를 남긴다. 의존 버전과 엔진 조회 결과는 `files`에 포함한 파일에 보존한다. 이 파일들은 빌드 fingerprint에 포함된다.

두 어댑터의 stdin은 `{"cases": [...]}` JSON이다. 입력 사례에는 `expected`/`expected_error`가 제거되어 있다. Wasm 어댑터에는 실제 컴파일된 파일의 절대 경로 `wasm`도 전달된다. stdout은 입력 사례에 실제 실행으로 얻은 `expected` 또는 `expected_error`를 추가한 JSON 배열이다. 로그는 stderr로 보낸다. 공개 계약에 합의된 반환/오류 매핑만 적용하고 근거를 기록한다.

현재 공통 비교는 **정확 일치이며 manifest cases 범위**다. fixture와 모든 가능한 입력의 동등성을 주장하지 않는다. 부동소수점 오차 비교가 필요한 경우 이 경로의 값을 반올림해 억지로 통과시키지 말고 해당 비교 기능을 확장하거나 미검증으로 남긴다. 기존 numeric/local 검증은 그대로 수행되지만 이 공통 원본 실행 증거로 자동 승격하지 않는다.

`artifacts/reference-verification.json`은 출처·실행 명령·파일 해시·원본/Wasm 결과와 Wasm 해시를 보존하고 전달 ZIP에도 포함된다. `status.py`의 `semantic_verification`은 기존 빌드/DB state와 독립적이다. 신규 증거가 없는 기존 프로젝트는 미검증이다.

이 프로토콜은 같은 입력·기대값 사용과 증거 결합을 검사한다. 어댑터가 실제 원본/실제 Wasm을 실행하는지, 출처가 진짜인지까지 자동 인증하지 않는다. 어댑터 검토와 원본 실행 로그를 `verification.md`에 남기고 최종 답변에는 실제 문서·소스 링크, 고정 버전, 실행 여부, 비교 범위와 증거 링크를 표시한다.
