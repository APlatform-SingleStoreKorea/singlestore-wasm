# SingleStore Wasm Skill for Codex

함수 이름·동작 설명이나 Python/Rust 코드를 바탕으로 **SingleStore용 Wasm 함수와 등록 SQL을 만드는 Codex 스킬**입니다. 행별 값을 계산하는 함수(UDF)와 여러 행을 집계하는 함수(UDAF)를 구현하며, 입력 코드와 대상 DB의 호환성을 확인해 구현 방식을 결정합니다.

스킬에는 구현 지침, 참조 문서, 빌드·검증 스크립트가 포함되어 있습니다. Codex가 이를 따라 적용 가능성을 판단하고, Rust 구현과 실제 Wasm 컴파일, Base64 변환, 등록 SQL·검증 SQL 생성까지 진행합니다. Python 입력은 코드와 의존성을 분석해 Rust로 이식하고, 원본 실행이 가능하면 결과를 비교합니다.

DB 접속 정보가 없어도 로컬 구현·빌드·SQL 생성까지 진행합니다. 실제 DB 등록·호출 검증은 접속 정보와 필요한 권한이 제공된 경우 수행합니다.

저장소: [APlatform-SingleStoreKorea/singlestore-wasm](https://github.com/APlatform-SingleStoreKorea/singlestore-wasm)

## 지원 환경

- 에이전트: Codex
- 문서화된 빌드 환경: Ubuntu, Python 3.12, Rust 1.85.0, `wasm32-unknown-unknown`
- 기본 대상 DB: SingleStore 9.1.1. 다른 버전을 요청하면 해당 버전의 호환성을 별도로 확인합니다.
- 입력: 함수 이름·동작 설명, Python 코드, Rust 코드

다른 언어나 실행 환경은 개별 분석과 검증이 필요합니다.

## 설치

### 1. 저장소 내려받기

Git이 설치된 터미널에서 공개 저장소를 내려받습니다.

```bash
git clone https://github.com/APlatform-SingleStoreKorea/singlestore-wasm.git
cd singlestore-wasm
```

### 2. Codex에 스킬 연결

Ubuntu 기준으로, 저장소 루트에서 아래 명령을 실행하면 사용자 공통 스킬 경로에 연결됩니다. 저장소 전체가 아니라 `SKILL.md`가 들어 있는 `skills/singlestore-wasm` 폴더를 연결합니다. 기존에 같은 이름의 스킬이 있다면 명령이 실패하므로, 기존 설치 위치를 먼저 확인하세요.

```bash
mkdir -p "$HOME/.agents/skills"
ln -sT "$PWD/skills/singlestore-wasm" "$HOME/.agents/skills/singlestore-wasm"
```

Codex는 `~/.agents/skills` 아래의 스킬과 심볼릭 링크를 인식합니다. 프로젝트에서만 사용하려면 해당 작업 프로젝트의 `.agents/skills/singlestore-wasm`에 연결할 수도 있습니다. 검색 경로는 [Codex 공식 스킬 문서](https://learn.chatgpt.com/docs/build-skills)를 참고하세요.

Codex에서 `singlestore-wasm`이 스킬 목록에 나타나는지 확인합니다. 나타나지 않으면 Codex를 다시 시작합니다. 연결된 저장소 폴더는 설치 후에도 유지해야 합니다.

### 3. 작업 환경 준비

스킬을 연결한 저장소와 별도로 쓰기 가능한 작업 폴더를 준비하고, 그 폴더에서 Codex를 사용합니다. Python 가상환경, 생성 프로젝트, 로그, DB 설정은 작업 폴더에 둡니다. 함수 생성 중에는 설치된 스킬 저장소를 수정하지 않습니다.

Rust toolchain과 Wasm target, Python 의존성 준비는 [환경 설정](skills/singlestore-wasm/references/workflow.md)을 따릅니다. Python 원본 비교에 필요한 추가 패키지는 입력 코드에 따라 준비합니다.

## 프롬프트 작성과 사용 예시

Codex에 **만들 함수의 이름·동작 또는 원본 코드**와 **SingleStore Wasm으로 구현해 달라는 요청**을 함께 전달합니다. 코드는 대화에 붙여 넣거나 Codex가 읽을 수 있는 작업 파일의 경로로 지정할 수 있습니다. 스킬을 직접 선택하려면 요청 앞에 `$singlestore-wasm`을 붙입니다.

등록 SQL과 검증 SQL 생성은 기본 작업에 포함되므로 따로 요청할 필요가 없습니다. 요구사항이 정해져 있다면 다음 정보를 함께 적어 주세요.

- 입력 인자와 원하는 반환 형식
- 대표 입력과 기대 결과, NULL·빈 입력 처리 방식
- 원본 함수의 라이브러리·버전 또는 참고 문서
- 대상 SingleStore 버전. 생략하면 9.1.1을 기준으로 진행합니다.

### 사용 예시

함수 이름으로 요청:

> retention 함수를 SingleStore Wasm 함수로 만들어줘.

동작을 설명하여 요청:

> 두 문자열의 편집 거리를 구하는 함수를 SingleStore Wasm 함수로 만들어줘.

Python 작업 파일을 지정하여 요청:

> `src/scoring.py`의 `calculate_score` 함수를 SingleStore Wasm 함수로 만들어줘. 입력과 반환 형식은 원본을 유지하고, 원본 실행 결과와 비교해줘.

Rust 코드를 첨부하고 스킬을 명시적으로 선택하여 요청:

> $singlestore-wasm 이 Rust 함수를 SingleStore Wasm 함수로 만들어줘.

Codex가 입력 코드와 함수 의미, SingleStore 호환성을 확인한 뒤 구현합니다. 원본과 공개 함수 개수·반환 형식·계산 의미가 달라져야 하는 경우에는 차이를 설명하고 선택을 확인합니다.

## 제공되는 결과물

성공적으로 생성된 결과는 파일 링크와 함께 제공합니다.

| 파일 | 용도 |
|---|---|
| `module.wasm` | 컴파일된 Wasm 바이너리 |
| `module.wasm.b64` | 실제 바이너리를 Base64로 변환한 파일 |
| `register.sql` | SingleStore 함수 등록 SQL |
| `validate.sql` | 정상·경계 사례의 결과를 확인하는 SQL |
| `validate-errors.sql` | 정의된 오류 사례를 확인하는 SQL. 사례가 없으면 해당 없음을 표시 |

Wasm 생성, Base64 변환, 원본 의미 비교, 실제 DB 검증 상태를 구분하여 보고합니다. 컴파일 성공만으로 DB 등록·호출까지 성공했다고 판단하지 않습니다. 자세한 보고 형식은 [최종 결과 형식](skills/singlestore-wasm/references/output-format.md)을 참고하세요.

## DB 등록과 검증

DB 검증이 필요하면 저장소 밖의 로컬 INI 파일에 접속 정보를 준비하고 Codex에 그 파일 경로와 대상 DB를 알려줍니다. 설정 형식과 필요한 권한은 [환경 설정](skills/singlestore-wasm/references/workflow.md)에 설명되어 있습니다.

접속 정보와 권한이 있으면 Codex가 등록·호출을 검증합니다. DB에 연결하지 못한 경우에는 미실행 또는 실패 이유와 생성된 SQL을 제공합니다. 직접 실행할 때는 `register.sql`, `validate.sql`, `validate-errors.sql` 순서로 사용합니다. 이미 등록된 함수는 등록 SQL을 반복 실행하지 말고 검증 SQL부터 사용합니다. 기존 이름과 충돌하는 함수를 자동으로 덮어쓰지 않습니다.

## 상세 문서

- [스킬 실행 절차](skills/singlestore-wasm/SKILL.md)
- [환경 설정](skills/singlestore-wasm/references/workflow.md)
- [지원 범위와 호환성](skills/singlestore-wasm/references/compatibility.md)
- [Python 코드 이식](skills/singlestore-wasm/references/python-porting.md)
- [설치와 갱신](docs/DISTRIBUTION.md)
- [기여 방법과 저장소 검증](CONTRIBUTING.md)
