pub mod logic;
pub mod json_array;
#[cfg(target_arch="wasm32")]
mod abi {
    use crate::logic::State;
    use std::alloc::{alloc,dealloc,realloc,Layout,handle_alloc_error};
    #[no_mangle]
    pub unsafe extern "C" fn canonical_abi_realloc(p:*mut u8,old:usize,align:usize,len:usize)->*mut u8 {
        if len==0 {if old>0 {dealloc(p,Layout::from_size_align_unchecked(old,align));} return align as *mut u8;}
        let layout=Layout::from_size_align_unchecked(len,align);
        let q=if old==0 {alloc(layout)} else {realloc(p,Layout::from_size_align_unchecked(old,align),len)};
        if q.is_null(){handle_alloc_error(layout);}q
    }
    #[no_mangle] pub unsafe extern "C" fn canonical_abi_free(p:*mut u8,len:usize,align:usize) {
        if len>0 {dealloc(p,Layout::from_size_align_unchecked(len,align));}
    }
    fn own(s:State)->i32 {Box::into_raw(Box::new(s)) as i32}
    unsafe fn take(h:i32)->Box<State> {Box::from_raw(h as *mut State)}
    unsafe fn input(p:*mut u8,n:usize)->Vec<u8> {if n==0 {Vec::new()} else {Vec::from_raw_parts(p,n,n)}}
    static mut AREA:[u32;2]=[0;2];
    unsafe fn output(bytes:Vec<u8>)->i32 {
        let len=bytes.len();let p=Box::into_raw(bytes.into_boxed_slice()) as *mut u8;
        let area=std::ptr::addr_of_mut!(AREA) as *mut u32;area.write(p as u32);area.add(1).write(len as u32);area as i32
    }
    #[export_name="agg-init"] pub extern "C" fn init()->i32 {own(State::default())}
    #[export_name="agg-step"] pub unsafe extern "C" fn step(h:i32,p:*mut u8,n:usize)->i32 {
        let bytes=input(p,n);let text=std::str::from_utf8(&bytes).expect("invalid_utf8");
        (*(h as *mut State)).add(text).unwrap();h
    }
    #[export_name="agg-merge"] pub unsafe extern "C" fn merge(a:i32,b:i32)->i32 {
        assert_ne!(a,b);let other=take(b);(*(a as *mut State)).merge(&other).unwrap();a
    }
    #[export_name="agg-copymerge"] pub unsafe extern "C" fn copymerge(a:i32,b:i32)->i32 {
        let mut s=(*(a as *const State)).clone();s.merge(&*(b as *const State)).unwrap();own(s)
    }
    #[export_name="agg-clone"] pub unsafe extern "C" fn clone(h:i32)->i32 {own((*(h as *const State)).clone())}
    #[export_name="agg-destroy"] pub unsafe extern "C" fn destroy(h:i32)->i32 {drop(take(h));0}
    #[export_name="agg-result"] pub unsafe extern "C" fn result(h:i32)->i32 {output(take(h).render().into_bytes())}
    #[export_name="agg-encode"] pub unsafe extern "C" fn encode(h:i32)->i32 {output(take(h).encode())}
    #[export_name="agg-decode"] pub unsafe extern "C" fn decode(p:*mut u8,n:usize)->i32 {own(State::decode(&input(p,n)).unwrap())}
}
