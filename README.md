# SingleStore Wasm

함수 이름·동작 설명 또는 Python/Rust 코드를 입력하면 SingleStore에서 사용할 Wasm 함수와 등록·검증 SQL을 만드는 Codex 스킬입니다.

**기본 대상: SingleStore 9.1.1**

[배포 ZIP 다운로드](singlestore-wasm.zip)

## 주요 기능

- 함수의 적용 가능성, 입력·출력 계약과 제약 분석
- Rust 구현과 실제 Wasm 컴파일
- Wasm 바이너리의 Base64 변환 및 등록 SQL 생성
- 로컬 테스트와 가능한 경우 원본 코드 실행 결과 비교
- 접속 정보와 작업 권한이 제공된 경우 실제 DB 등록·호출 검증

Python 코드는 원본 의미를 분석해 Rust로 이식합니다. 모든 Python 프로그램을 자동으로 변환하는 범용 번역기는 아닙니다.

## 설치

### 1. 스킬 압축 해제

이 저장소의 `singlestore-wasm.zip`을 다운로드합니다. GitHub 파일 화면에서는 **Download raw file**로 받을 수 있습니다.

사용할 프로젝트의 루트에서 다음 명령을 실행합니다. `/path/to/singlestore-wasm.zip`은 다운로드한 ZIP의 실제 경로로 바꿉니다.

```bash
mkdir -p .agents/skills
unzip /path/to/singlestore-wasm.zip -d .agents/skills
```

설치 후 다음 파일이 있어야 합니다.

```text
프로젝트/
└── .agents/skills/singlestore-wasm/
    ├── SKILL.md
    ├── README.md
    ├── scripts/
    ├── templates/
    └── references/
```

기존 설치가 있다면 보관한 뒤 새 버전으로 교체하세요.

### 2. 실행 환경 준비

기준 환경은 Ubuntu와 Python 3.12입니다. 아래 명령은 Python 3.12의 venv 기능과 Rustup이 설치되어 있다고 가정합니다.

프로젝트 루트에서 실행합니다.

```bash
rustup toolchain install 1.85.0 --profile minimal
rustup target add wasm32-unknown-unknown --toolchain 1.85.0

python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r .agents/skills/singlestore-wasm/requirements.txt
```

Python 원본 비교에 필요한 추가 패키지는 다음 목록으로 설치할 수 있습니다. 입력 코드에 따라 별도 의존성이 필요할 수 있습니다.

```bash
python -m pip install -r .agents/skills/singlestore-wasm/requirements-python.txt
```

일부 C++ 원본 비교에는 `g++`가 추가로 필요합니다. 상세 환경 안내는 압축 해제한 스킬의 `references/workflow.md`에 있습니다.

## 사용 예시

스킬을 설치한 프로젝트를 Codex에서 열고 요청합니다.

**함수명으로 요청**

```text
Levenshtein 거리 함수를 SingleStore Wasm 함수로 구현해줘.
```

**기존 코드로 요청**

```text
아래 코드를 SingleStore Wasm 함수로 변환해줘.

[원본 코드]
```

함수별 입력·출력과 원본 동작을 검토한 뒤 새 프로젝트에 구현하고 빌드합니다. 호출 방식·반환 형식·계산 의미에 변경이 필요한 경우에는 차이를 설명하고 확인합니다.

## 생성 결과

생성 프로젝트의 `artifacts/`에 다음 주요 파일이 저장됩니다.

| 파일 | 용도 |
|---|---|
| `module.wasm` | 실제 컴파일한 Wasm 바이너리 |
| `module.wasm.b64` | Wasm의 Base64 표현 |
| `register.sql` | SingleStore 함수 등록 |
| `validate.sql` | 정상 입력의 실제값·기대값 비교 |
| `validate-errors.sql` | 정의된 오류 사례 검증 |

소스 코드와 함수 계약, 빌드 로그 및 검증 보고서도 함께 생성됩니다. Cargo 빌드 과정에서는 생성 프로젝트에 `target/` 폴더가 생깁니다.

**로컬 빌드 성공과 실제 DB 검증 성공은 별도입니다.** DB에 접속하지 않은 결과는 DB 미검증으로 표시합니다. 원본 비교 역시 실제 수행 여부와 검증 범위를 구분해 보고합니다.

## DB 검증

DB 접속 정보가 없어도 로컬 구현·빌드와 등록 SQL 생성은 가능합니다. 실제 DB 등록·호출은 접속 정보가 제공되고 해당 작업이 허용된 경우에 수행합니다.

접속 정보는 로컬 설정 파일로 관리하며 저장소에 올리지 않습니다. 기존 DB 객체와 이름이 충돌하면 중단하고, 기존 객체를 자동으로 덮어쓰지 않습니다. 연결 실패 후에는 같은 빌드로 재시도할 수 있으며 실행별 검증 기록을 보존합니다.

수동 실행 시에는 `register.sql`로 등록한 뒤 검증 SQL을 실행합니다. 이미 등록된 함수라면 등록 SQL을 반복 실행하지 말고 검증 SQL부터 사용하세요.

## 이 저장소의 구성

이 저장소는 배포용 ZIP과 사용 안내를 제공합니다. 스킬의 실행 코드·템플릿·상세 문서는 ZIP에 포함되어 있습니다.

