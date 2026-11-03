"""Local verifier for the synthetic mixed HANDLE regression fixture only."""
import json
import sys
from pathlib import Path

def main():
    # Execute HANDLE callbacks independently of SQL. No live registration asserted.
    import wasmtime
    e=wasmtime.Engine();s=wasmtime.Store(e);mod=wasmtime.Module(e,Path(sys.argv[1]).read_bytes());x=wasmtime.Instance(s,mod,[]).exports(s)
    def alloc(b):
        p=x['canonical_abi_realloc'](s,0,0,1,len(b));x['memory'].write(s,b,p);return p,len(b)
    def output(addr):
        import struct
        p,n=struct.unpack('<II',bytes(x['memory'].read(s,addr,addr+8)));return bytes(x['memory'].read(s,p,p+n))
    assert output(x['agg-result'](s,x['agg-init'](s)))==b'0'
    a=x['agg-init'](s);a=x['agg-step'](s,a,*alloc(b'[true,false,true]'),3)
    b=x['agg-init'](s);b=x['agg-step'](s,b,*alloc(b'[true]'),2)
    cloned=x['agg-clone'](s,a);encoded=output(x['agg-encode'](s,cloned));restored=x['agg-decode'](s,*alloc(encoded))
    assert output(x['agg-result'](s,restored))==b'6'
    combined=x['agg-copymerge'](s,a,b);assert output(x['agg-result'](s,combined))==b'8'
    merged=x['agg-merge'](s,a,b);assert output(x['agg-result'](s,merged))==b'8'
    doomed=x['agg-init'](s);assert x['agg-destroy'](s,doomed)==0
    for invalid in (b'[null]', b'[1]', b'[true,]', b'{}', b'['+b','.join([b'true']*11)+b']'):
        fresh=wasmtime.Store(e);fx=wasmtime.Instance(fresh,mod,[]).exports(fresh)
        ptr=fx['canonical_abi_realloc'](fresh,0,0,1,len(invalid));fx['memory'].write(fresh,invalid,ptr)
        try: fx['agg-step'](fresh,fx['agg-init'](fresh),ptr,len(invalid),1)
        except wasmtime.Trap: pass
        else: raise AssertionError('invalid repeat input accepted')
    print(json.dumps({'status':'passed','merge':'passed','serialization':'passed','empty':'passed','clone_copymerge_destroy':'passed'}))

if __name__=='__main__': main()
