# Architecture

## 구조

이 저장소는 Codex에서 사용하는 `singlestore-wasm` 스킬 하나를 관리합니다.

```text
singlestore-wasm/
├── skills/singlestore-wasm/
│   ├── SKILL.md
│   ├── references/
│   ├── scripts/
│   └── templates/
├── scripts/                 # 저장소 검사와 manifest 생성
├── tests/                   # 공통 도구 테스트와 activation fixture
└── dist/skills-manifest.json
```

```text
GitHub APlatform-SingleStoreKorea/singlestore-wasm
  -> 로컬 checkout
  -> Codex .agents/skills 경로의 심볼릭 링크
  -> name/description으로 스킬 탐색
  -> 선택된 SKILL.md와 연결된 지원 파일 읽기
  -> 별도 작업 폴더에서 함수 생성·빌드·검증
```

## 저장소 범위

이 저장소는 SingleStore Wasm 함수 생성·검증 절차를 관리합니다. SingleStore 클러스터 설치나 쿼리 튜닝 스킬은 포함하지 않습니다.

## 유지할 규칙

- 스킬 이름: `singlestore-wasm`
- 진입점: `skills/singlestore-wasm/SKILL.md`
- 생성된 manifest와 스킬 본문 해시
- positive/negative activation fixture
- PR을 통한 변경 검토
- 사용 중인 checkout과 기여 작업공간 분리

설치와 갱신은 [DISTRIBUTION.md](DISTRIBUTION.md), 기여 절차는 [CONTRIBUTING.md](../CONTRIBUTING.md)를 참고합니다.
