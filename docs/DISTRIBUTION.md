# Codex 설치와 갱신

현재 지원하는 에이전트는 Codex입니다. 설치 절차는 [README](../README.md#설치)를 따릅니다.

GitHub의 [singlestore-wasm](https://github.com/APlatform-SingleStoreKorea/singlestore-wasm) 저장소를 clone한 뒤, `skills/singlestore-wasm`을 `~/.agents/skills/singlestore-wasm`에 심볼릭 링크로 연결합니다. 특정 프로젝트에서만 사용하려면 그 프로젝트의 `.agents/skills/singlestore-wasm`에 연결합니다. 저장소 루트 전체가 아니라 `SKILL.md`가 들어 있는 스킬 폴더를 연결해야 합니다.

함수 생성 중에는 설치된 checkout을 수정하지 않습니다. 가상환경·생성 프로젝트·로그·DB 설정은 별도 작업 폴더에 둡니다. 매 요청마다 저장소를 다시 clone할 필요는 없습니다.

## 갱신

1. 설치된 checkout의 로컬 변경 유무와 연결된 GitHub remote를 확인합니다.
2. 로컬 변경을 덮어쓰지 않고 `main`의 변경을 fast-forward 방식으로 가져옵니다. 고정 커밋으로 운영한다면 검토한 커밋으로 갱신합니다.
3. [기여 문서의 저장소 검증](../CONTRIBUTING.md#저장소-검증)을 실행합니다. manifest 재생성 후 예상하지 않은 변경이 생기면 사용 전에 원인을 확인합니다.
4. checkout 경로가 같으면 심볼릭 링크는 그대로 사용합니다. 경로를 옮겼다면 링크 대상도 갱신합니다.
5. Codex에서 스킬 인식을 확인합니다. 변경이 반영되지 않으면 Codex를 다시 시작하고 새 세션에서 대표 요청의 스킬 선택을 확인합니다.

검색 경로와 심볼릭 링크 지원은 [Codex 공식 스킬 문서](https://learn.chatgpt.com/docs/build-skills)를 참고하세요.
