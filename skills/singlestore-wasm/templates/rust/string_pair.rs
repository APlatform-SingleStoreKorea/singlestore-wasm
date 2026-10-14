// SingleStore's legacy CANONICAL ABI, not the modern component ABI.
// Ownership/signatures match wit-bindgen revision
// 60e3c5b41e616fee239304d92128e117dd9be0a7 (see references/abi.md).
#[cfg(target_arch = "wasm32")]
mod abi {
    use std::alloc::{alloc, dealloc, handle_alloc_error, realloc, Layout};

    #[no_mangle]
    pub unsafe extern "C" fn canonical_abi_realloc(
        old_ptr: *mut u8, old_len: usize, align: usize, new_len: usize,
    ) -> *mut u8 {
        if new_len == 0 {
            if old_len != 0 {
                dealloc(old_ptr, Layout::from_size_align_unchecked(old_len, align));
            }
            return align as *mut u8;
        }
        let layout = Layout::from_size_align_unchecked(new_len, align);
        let ptr = if old_len == 0 {
            alloc(layout)
        } else {
            realloc(old_ptr, Layout::from_size_align_unchecked(old_len, align), new_len)
        };
        if ptr.is_null() { handle_alloc_error(layout); }
        ptr
    }

    #[no_mangle]
    pub unsafe extern "C" fn canonical_abi_free(ptr: *mut u8, len: usize, align: usize) {
        if len != 0 { dealloc(ptr, Layout::from_size_align_unchecked(len, align)); }
    }

    unsafe fn lift(ptr: *mut u8, len: usize) -> String {
        if len == 0 { return String::new(); }
        // Host allocates each distinct argument with realloc(len, alignment=1).
        // The guest owns these buffers and drops them at the end of evaluate.
        String::from_utf8(Vec::from_raw_parts(ptr, len, len)).expect("invalid UTF-8")
    }

    #[export_name = "evaluate"]
    pub unsafe extern "C" fn evaluate_export(a: *mut u8, an: usize, b: *mut u8, bn: usize) -> i64 {
        let left = lift(a, an);
        let right = lift(b, bn);
        crate::logic::evaluate(&left, &right)
    }
}
