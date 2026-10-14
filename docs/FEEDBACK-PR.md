# Verified Skill Improvement PR

Registry와 Resolver 없이도 Agent가 Skill 개선 PR을 만들 수 있습니다. 필요한 것은 원본 Git remote, Skill path, 전용 branch push 권한입니다.

```text
Skill 실행 중 문제 발견
  -> 실패와 수정 성공 근거 확보
  -> 원본 remote/path 확인
  -> 별도 contribution clone
  -> 최소 수정
  -> 구조 검증 + workflow smoke test
  -> branch push
  -> GitHub PR
  -> human merge
```

## 작업공간

```text
~/.agents/skills/singlestore-wasm   # 사용본 checkout의 스킬 폴더로 연결
별도 contribution clone/          # GitHub PR 작업용
```

사용본을 직접 수정하지 않습니다.
사용 checkout과 Git metadata를 공유하는 worktree도 사용하지 않습니다.

## 권한

Agent identity에는 Repo read, 전용 branch push, PR create만 부여합니다. `main` direct push, merge, branch protection 변경, 관리자 권한은 주지 않습니다.

## PR 대상

다음만 PR로 제출합니다.

- 명시적인 사용자 교정
- 기존 절차 실패와 대체 절차 성공이 확인된 경우
- 누락된 prerequisite, verification, safety pitfall

Transient 상태, host 정보, secret, 프로젝트 전용 값, 검증되지 않은 추측은 제출하지 않습니다.
