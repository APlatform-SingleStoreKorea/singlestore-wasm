# 검증 프로필과 legacy Canonical ABI

WIT는 modern component `world`가 아닌 standalone 형식이다.

```wit
evaluate: func(left: string, right: string) -> s64
```

문서 예제가 고정한 wit-bindgen 커밋 `60e3c5b41e616fee239304d92128e117dd9be0a7`의 [ABI lowering](https://github.com/bytecodealliance/wit-bindgen/blob/60e3c5b41e616fee239304d92128e117dd9be0a7/crates/parser/src/abi.rs), [Rust lifting](https://github.com/bytecodealliance/wit-bindgen/blob/60e3c5b41e616fee239304d92128e117dd9be0a7/crates/gen-rust-wasm/src/lib.rs), [allocator](https://github.com/bytecodealliance/wit-bindgen/blob/60e3c5b41e616fee239304d92128e117dd9be0a7/crates/rust-wasm/src/lib.rs)를 기준으로 작은 수동 바인딩을 작성했다. 외부 crate 또는 해당 저장소를 빌드 의존성으로 사용하지 않는다.

문자열은 `(i32 pointer, i32 UTF-8 byte length)`, s64는 i64다. 두 문자열→s64 export는 `(i32,i32,i32,i32)->i64`. host가 guest의 `canonical_abi_realloc(old_ptr,old_len,align,new_len)`으로 입력을 할당하고, guest가 인자를 소유하고 drop한다. `canonical_abi_free(ptr,len,align)`도 export한다. 길이 0은 역참조하지 않는다. 포인터/길이는 신뢰된 ABI host가 준다는 unsafe 전제가 있다. 임의 foreign caller의 악의적인 포인터 검증을 제공하지 않는다.

복합 타입, 반환 문자열, option, list, record, 많은 인자는 추가 ABI 구현을 요구한다. 이 stub에 WIT만 교체하지 않는다. NULL은 SQL wrapper로 처리하므로 direct option ABI 매핑은 미검증이다. internal core를 직접 호출하면 public NULL/오류 계약이 적용되지 않는다.

WIT를 쓰는 등록은 **implicit typing**이다. SQL 인자/RETURNS 선언을 core CREATE와 혼합하면 구문 오류가 난다. public SQL wrapper에 명시적 utf8mb4·NULL 타입을 둔다. `USING EXPORT 'evaluate'`, `ABI CANONICAL`, `GROW TO 16777216`을 지정한다.

Rust 1.85.0 / Cargo 1.85.0 / LLVM 19.1.7 / wasm32-unknown-unknown / Rust crate dependencies 0을 검증 프로필로 고정한다. [old wasm32-wasi 변경](https://blog.rust-lang.org/2024/04/09/updates-to-rusts-wasi-targets/)과 [unknown-unknown 제약](https://doc.rust-lang.org/rustc/platform-support/wasm32-unknown-unknown.html)을 참고한다. 최신 Rust로 변경하면 생성된 명령·표준 라이브러리 기능도 달라질 수 있어 DB 재검증이 필요하다.

기본 빌드 설정은 Wasm max memory 16 MiB, stack 256 KiB이며 함수별 manifest의 build로 변경할 수 있다. `inspect_wasm.py`는 import/export/memory/signature의 구조 검사만 한다. instruction validation과 엔진 지원 기능 전체를 증명하지 않는다. 실제 DB 등록과 호출이 별도의 필수 단계다.

HANDLE string ITERATE는 `(state s32, string) -> state`가 `(i32,i32,i32)->i32`로 낮아진다. guest가 문자열 입력을 소유·해제한다. SQL 입력은 명시적 TEXT utf8mb4_bin NOT NULL이며 새 ITERATE 프로필의 DB 등록은 미검증이다. [입력 계약](json-condition-array.md)을 참고한다.
