"""Read generated SQL files, including client DELIMITER directives.

This parser supports the generator's single/double quoted strings, backtick
identifiers and whole-line comments. Unsupported/unfinished input fails closed.
"""
import hashlib


def read_statements(path):
    text = path.read_text(encoding='utf-8')
    delimiter = ';'
    buffer = ''
    quote = None
    statements = []
    for line in text.splitlines(keepends=True):
        if quote is None and not buffer.strip():
            if line.lstrip().startswith('--') or not line.strip():
                continue
            if line.strip().upper().startswith('DELIMITER '):
                delimiter = line.strip().split(None, 1)[1]
                if delimiter not in (';', '//'):
                    raise ValueError('unsupported delimiter')
                continue
        i = 0
        while i < len(line):
            ch = line[i]
            if quote:
                buffer += ch
                if ch == '\\' and quote != '`' and i + 1 < len(line):
                    i += 1
                    buffer += line[i]
                elif ch == quote:
                    if i + 1 < len(line) and line[i+1] == quote:
                        i += 1
                        buffer += line[i]
                    else:
                        quote = None
                i += 1
            elif line.startswith(delimiter, i):
                if buffer.strip():
                    statements.append(buffer.strip())
                buffer = ''
                i += len(delimiter)
            else:
                buffer += ch
                if ch in "'\"`":
                    quote = ch
                i += 1
    if quote or buffer.strip():
        raise ValueError('unterminated SQL in ' + str(path))
    return statements


def validation_items(path, checks, errors=False):
    statements = read_statements(path)
    if not statements or statements.pop(0).upper() != 'SET NAMES UTF8MB4':
        raise ValueError('missing UTF-8 setup in ' + str(path))
    selected = [item for item in checks if ('expected_error' in item['case']) == errors]
    if len(statements) != len(selected):
        raise ValueError('SQL file case count mismatch: ' + str(path))
    return [{'case': item['case'], 'sql': sql} for item, sql in zip(selected, statements)]


def file_evidence(path, count):
    return {'status': 'passed', 'statements': count,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'path': str(path)}
