---
name: singlestore-workflow-name
description: Use when performing a SingleStore workflow.
version: 1.0.0
author: Consulting Team
license: Proprietary
metadata:
  org:
    tags: [singlestore, workflow]
    required_capabilities: [shell]
---

# Workflow Name

## Overview

표준화하는 반복 workflow와 최종 결과를 짧게 설명합니다.

## When to Use

- 정확한 사용자 요청 class를 적습니다.
- 같은 workflow의 복구 또는 검증 요청을 적습니다.

## Do Not Use

- 가장 가까운 이웃 workflow를 적습니다.
- 지원하지 않는 환경이나 위험 등급을 적습니다.

## Prerequisites

1. 대상, 환경, 버전, 원하는 결과를 확인합니다.
2. 필요한 capability와 인증의 존재를 값 노출 없이 확인합니다.
3. 승인 또는 작업 시간이 필요한지 확인합니다.

완료 조건: 대상, 범위, 권한, 복구 기준이 명확합니다.

## Procedure

1. authoritative read-only 방법으로 현재 상태를 확인합니다.

   완료 조건: 현재 상태와 원하는 변경의 차이가 명확합니다.

2. 이 Skill package의 checked-in preflight가 있으면 실행합니다.

   완료 조건: 모든 blocking check가 통과합니다. 실패하면 정확한 blocker를 보고하고 중단합니다.

3. 승인된 최소 변경을 적용합니다.

   완료 조건: 명령 성공뿐 아니라 authoritative state가 원하는 상태를 반영합니다.

4. 변경 후 검증과 사용자 관점 smoke test를 실행합니다.

   완료 조건: 시스템 상태와 기능 동작이 모두 통과합니다.

## Failure and Rollback

- 대상이 모호하거나 prerequisite가 없으면 중단합니다.
- exit code만으로 성공을 선언하지 않습니다.
- 변경 후 검증 실패 시 승인된 rollback을 수행하고 이전 상태를 확인합니다.
- identifier, credential, command, output을 추측하지 않습니다.

## Common Pitfalls

1. **Wrong target:** inspect와 apply에서 같은 대상과 환경을 확인합니다.
2. **Mutable version:** 가능한 경우 immutable version이나 release를 사용합니다.
3. **No verification:** authoritative state와 functional test를 모두 확인합니다.
4. **Secret leakage:** raw credential을 출력, 문서, PR에 넣지 않습니다.
5. **Local drift:** 검증된 개선은 원본 Repo의 PR로 제안합니다.

## Verification Checklist

- [ ] 대상, 환경, 버전 확인
- [ ] 필요한 권한 확인
- [ ] preflight 통과
- [ ] 요청된 상태 적용
- [ ] authoritative state 확인
- [ ] functional smoke test 통과
- [ ] rollback 가능
- [ ] 결과에 secret 없음

## References

지원 파일이 있을 때만 경로와 로드 조건을 적습니다.
