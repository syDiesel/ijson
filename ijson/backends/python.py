from decimal import Decimal
import re

from ijson import common


BUFSIZE = 16 * 1024
NONWS = re.compile(r'\S')
LEXTERM = re.compile(r'[^a-z0-9\.-]')


class UnexpectedSymbol(common.JSONError):
    def __init__(self, symbol, reader):
        super(UnexpectedSymbol, self).__init__('Unexpected symbol "%s" at %d' % (symbol[0], reader.pos - len(symbol)))

class Reader(object):
    def __init__(self, f):
        self.f = f

    def __iter__(self):
        self.buffer = ''
        self.pos = 0
        return self

    def next(self):
        while True:
            match = NONWS.search(self.buffer, self.pos)
            if match:
                self.pos = match.start()
                char = self.buffer[self.pos]
                if 'a' <= char <= 'z' or '0' <= char <= '9' or char == '-':
                    return self.lexem()
                elif char == '"':
                    return self.stringlexem()
                else:
                    self.pos += 1
                    return char
            self.buffer = self.f.read(BUFSIZE)
            self.pos = 0
            if not len(self.buffer):
                raise common.IncompleteJSONError()

    def lexem(self):
        current = self.pos
        while True:
            match = LEXTERM.search(self.buffer, current)
            if match:
                current = match.start()
                break
            else:
                current = len(self.buffer)
                self.buffer += self.f.read(BUFSIZE)
                if len(self.buffer) == current:
                    break
        result = self.buffer[self.pos:current]
        self.pos = current
        if self.pos > BUFSIZE:
            self.buffer = self.buffer[self.pos:]
            self.pos = 0
        return result

    def stringlexem(self):
        start = self.pos + 1
        while True:
            try:
                end = self.buffer.index('"', start)
                escpos = end - 1
                while self.buffer[escpos] == '\\':
                    escpos -= 1
                if (end - escpos) % 2 == 0:
                    start = end + 1
                else:
                    result = self.buffer[self.pos:end + 1]
                    self.pos = end + 1
                    return result
            except ValueError:
                old_len = len(self.buffer)
                self.buffer += self.f.read(BUFSIZE)
                if len(self.buffer) == old_len:
                    raise common.IncompleteJSONError()

def parse_value(f, symbol=None):
    if symbol == None:
        symbol = f.next()
    if symbol == 'null':
        yield ('null', None)
    elif symbol == 'true':
        yield ('boolean', True)
    elif symbol == 'false':
        yield ('boolean', False)
    elif symbol == '[':
        for event in parse_array(f):
            yield event
    elif symbol == '{':
        for event in parse_object(f):
            yield event
    elif symbol[0] == '"':
        yield ('string', symbol[1:-1].decode('unicode-escape'))
    else:
        try:
            number = Decimal(symbol) if '.' in symbol else int(symbol)
            yield ('number', number)
        except ValueError:
            raise UnexpectedSymbol(symbol, f)

def parse_array(f):
    yield ('start_array', None)
    symbol = f.next()
    if symbol != ']':
        while True:
            for event in parse_value(f, symbol):
                yield event
            symbol = f.next()
            if symbol == ']':
                break
            if symbol != ',':
                raise UnexpectedSymbol(symbol, f)
            symbol = f.next()
    yield ('end_array', None)

def parse_object(f):
    yield ('start_map', None)
    symbol = f.next()
    if symbol != '}':
        while True:
            if symbol[0] != '"':
                raise UnexpectedSymbol(symbol, f)
            yield ('map_key', symbol[1:-1])
            symbol = f.next()
            if symbol != ':':
                raise UnexpectedSymbol(symbol, f)
            for event in parse_value(f):
                yield event
            symbol = f.next()
            if symbol == '}':
                break
            if symbol != ',':
                raise UnexpectedSymbol(symbol, f)
            symbol = f.next()
    yield ('end_map', None)

def basic_parse(f):
    f = iter(Reader(f))
    for value in parse_value(f):
        yield value
    try:
        f.next()
    except common.IncompleteJSONError:
        pass
    else:
        raise common.JSONError('Additional data')

def parse(file):
    return common.parse(basic_parse(file))

def items(file, prefix):
    return common.items(parse(file), prefix)
