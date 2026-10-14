"""Inspect core Wasm imports/exports/memory without third party tools.

This is a structural inventory, not an instruction-level Wasm validator.
SingleStore registration and execution remain the compatibility authority.
"""
class Reader:
    def __init__(self, data): self.data, self.pos = data, 0
    def byte(self):
        b = self.data[self.pos]; self.pos += 1; return b
    def uint(self):
        value, shift = 0, 0
        while True:
            b = self.byte(); value |= (b & 127) << shift
            if not b & 128: return value
            shift += 7
            if shift > 35: raise ValueError('invalid u32 LEB')
    def take(self, n):
        data = self.data[self.pos:self.pos+n]; self.pos += n
        if len(data) != n: raise ValueError('truncated Wasm')
        return data
    def string(self): return self.take(self.uint()).decode()

def inspect(data):
    if data[:8] != b'\x00asm\x01\x00\x00\x00': raise ValueError('expected core Wasm version 1')
    r = Reader(data[8:]); result = {'imports': [], 'exports': [], 'memories': []}
    types, functions = [], []
    names = {0x7f:'i32', 0x7e:'i64', 0x7d:'f32', 0x7c:'f64'}
    while r.pos < len(r.data):
        kind = r.byte(); section = Reader(r.take(r.uint()))
        if kind == 1:
            for _ in range(section.uint()):
                if section.byte() != 0x60: raise ValueError('unsupported non-function Wasm type')
                args = [names[section.byte()] for _ in range(section.uint())]
                returns = [names[section.byte()] for _ in range(section.uint())]
                types.append({'parameters': args, 'results': returns})
        elif kind == 2:
            if section.uint() != 0:
                raise ValueError('this pure-function build profile forbids host imports')
        elif kind == 3:
            functions = [section.uint() for _ in range(section.uint())]
        elif kind == 5:
            for _ in range(section.uint()):
                flags = section.uint(); minimum = section.uint()
                maximum = section.uint() if flags & 1 else None
                result['memories'].append({'min_pages': minimum, 'max_pages': maximum, 'flags': flags})
        elif kind == 7:
            for _ in range(section.uint()):
                name, export_kind, index = section.string(), section.byte(), section.uint()
                item = {'name': name, 'kind': export_kind, 'index': index}
                if export_kind == 0: item.update(types[functions[index]])
                result['exports'].append(item)
    return result
