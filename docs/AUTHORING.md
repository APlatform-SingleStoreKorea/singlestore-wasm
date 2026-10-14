# Skill Authoring

## 단위

Skill 하나는 반복 가능한 workflow 하나를 담당합니다. 사용자가 독립적으로 요청하지 않는 내부 단계는 별도 Skill로 만들지 말고 support script로 둡니다.

## 이름

`skill-repo.json`의 `name_prefix`로 시작하는 lowercase kebab-case를 사용합니다.

```text
<org>-<product-or-domain>-<workflow>
```

디렉터리명, frontmatter `name`, activation fixture 이름을 동일하게 유지합니다.

## Frontmatter

```yaml
---
name: singlestore-workflow
description: Use when performing the SingleStore workflow.
version: 1.0.0
author: Consulting Team
license: Proprietary
metadata:
  org:
    tags: [singlestore, workflow]
    required_capabilities: [shell]
---
```

특정 Runtime 필드는 공통 `metadata.org`와 분리된 선택적 확장으로만 추가합니다.

## 본문

```text
Overview
When to Use
Do Not Use
Prerequisites
Procedure
Failure and Rollback
Common Pitfalls
Verification Checklist
References
```

각 단계에는 확인 가능한 완료 조건을 둡니다.

## Support files

- `references/`: 버전별 문서, 정책, troubleshooting
- `templates/`: 실행 입력과 결과 형식
- `scripts/`: 반복 가능한 검사와 실행
- `assets/`: 비지시성 보조 자료

지원 파일은 `SKILL.md`에서 언제 읽거나 실행할지 명시합니다. Runtime 전용 절대경로나 환경 변수를 공통 절차에 넣지 않습니다.

## Activation fixture

`tests/activation/<name>.json`에 positive와 가장 가까운 negative 요청을 각각 2개 이상 둡니다. 저장소 검사 도구는 형식만 검사하며 실제 선택은 배포 후 fresh session에서 확인합니다.

## 비밀과 환경 정보

호스트, IP, 계정, credential 값, private key, token, transient inventory는 커밋하지 않습니다. 필요한 credential은 이름 또는 외부 reference만 선언합니다.
