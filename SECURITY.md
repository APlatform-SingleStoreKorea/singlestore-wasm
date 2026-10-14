# Security

- 저장소 접근은 지정된 작성자, reviewer, Agent identity로 제한합니다.
- raw token, password, private key, OAuth secret, credential file을 Skill과 PR에 넣지 않습니다.
- 내부 hostname, network topology, account identifier도 기밀 정보로 취급합니다.
- 소비 Agent는 read-only credential을 사용합니다.
- PR 생성 identity와 기본 브랜치 merge 권한을 분리합니다.
- 배포는 보호된 기본 브랜치의 특정 commit SHA를 기준으로 합니다.
- 보안 문제가 의심되면 공개 issue 대신 조직의 지정된 보안 신고 채널을 사용합니다.

`scripts/validate_skills.py`의 pattern scan은 보조 검사입니다. 조직에서 사용하는 별도의 보안 검사 도구를 대체하지 않습니다.
