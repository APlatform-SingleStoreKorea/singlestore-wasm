# Contributing

모든 변경은 PR로 제출합니다.

PR에는 다음만 포함합니다.

- 변경 대상 Skill
- 변경 이유와 재현 가능한 근거
- positive/negative activation fixture
- 구조 검증 및 workflow smoke test 결과
- secret과 환경 고유 값 미포함 확인

리뷰 기준:

1. 기존 Skill과 중복되지 않는가
2. 선택/비선택 경계가 명확한가
3. 단계마다 확인 가능한 완료 조건이 있는가
4. 실패·중단·복구 기준이 있는가
5. 명령과 검증이 재현 가능한가

## 저장소 검증

저장소 루트에서 다음 명령을 실행합니다.

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
python3 scripts/build_manifest.py
python3 scripts/validate_skills.py
git diff --check
```

이 검사는 저장소 구조, activation fixture 형식과 공통 검사 도구를 확인합니다. 실제 Codex 스킬 선택, Wasm 컴파일, DB 등록·호출 검증은 별도로 수행하며 실제로 확인한 범위를 PR에 기록합니다.

작성 규칙은 [AUTHORING.md](docs/AUTHORING.md), 검증된 스킬 개선 절차는 [FEEDBACK-PR.md](docs/FEEDBACK-PR.md)를 따릅니다.
