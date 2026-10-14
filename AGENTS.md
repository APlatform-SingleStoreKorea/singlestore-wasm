# Agent Contribution Rules

이 저장소에서 Skill을 만들거나 수정하는 Agent는 다음을 지킵니다.

1. `skill-repo.json`, `docs/AUTHORING.md`, 관련 기존 Skill을 먼저 읽습니다.
2. 같은 workflow가 이미 있는지 `skills/`와 Manifest에서 확인합니다.
3. `templates/SKILL.md`를 복사하고 디렉터리명, frontmatter `name`, activation fixture 이름을 맞춥니다.
4. `description`은 `Use when ...`으로 시작하는 짧고 완전한 trigger로 작성합니다.
5. 항상 필요한 절차만 `SKILL.md`에 두고 나머지는 명시적으로 연결된 support file로 분리합니다.
6. `tests/activation/<name>.json`에 positive와 negative prompt를 각각 2개 이상 작성합니다.
7. 실행으로 확인하지 않은 명령, 결과, 복구 절차를 만들지 않습니다.
8. raw token, password, private key, OAuth secret, credential file을 커밋하지 않습니다.
9. 변경 후 다음을 실행합니다.

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
python3 scripts/build_manifest.py
python3 scripts/validate_skills.py
git diff --check
```

변경 후에는 `scripts/build_manifest.py`로 manifest를 재생성합니다.

## Verified Improvement PR

Skill 실행 중 재사용 가능한 오류를 발견했을 때만 개선을 제안합니다.

1. 기존 절차의 실패와 수정 절차의 성공 근거를 확보합니다.
2. 사용 중인 read-only checkout은 수정하지 않습니다.
3. 원본 Git remote와 Skill path를 확인하고 별도 contribution clone을 만듭니다. 사용 checkout과 Git metadata를 공유하는 worktree는 사용하지 않습니다.
4. 검증된 문제만 최소 diff로 수정합니다.
5. 위 검증 명령과 실제 workflow smoke test를 실행합니다.
6. 전용 branch를 push하고 GitHub PR을 생성합니다.
7. PR에는 원인, 수정, 검증 결과를 적고 merge는 reviewer에게 맡깁니다.

Transient host 정보, secret, 프로젝트 전용 상태, 추측한 개선은 PR에 넣지 않습니다. 기본 브랜치에 직접 push하거나 자동 merge하지 않습니다.
