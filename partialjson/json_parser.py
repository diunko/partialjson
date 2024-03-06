import json

dbg = False


class JSONParser:
    def __init__(self):
        self._parser_stack = []
        self._path = []
        self._original_exception = None

        self.parsers = {
            ' ': self.parse_space,
            '\r': self.parse_space,
            '\n': self.parse_space,
            '\t': self.parse_space,
            '[': self.parse_array,
            '{': self.parse_object,
            '"': self.parse_string,
            't': self.parse_true,
            'f': self.parse_false,
            'n': self.parse_null
        }
        # Adding parsers for numbers
        for c in '0123456789.-':
            self.parsers[c] = self.parse_number

        self.last_parse_remainder = None
        self.on_extra_token = self.default_on_extra_token

    def get_parser(self, s):
        p = self.parsers.get(s[0])
        assert p is not None, f"Can't get parser for '{s}'"
        self._push(p.__name__)
        return p

    def _push(self, name):
        self._parser_stack.append(name)
        dbg and print('push', self._parser_stack)

    def _pop(self, name):
        assert self._parser_stack[-1] == name, f'{(self._parser_stack, name) =}'
        self._parser_stack.pop(-1)
        dbg and print('pop', self._parser_stack)

    def default_on_extra_token(self, text, data, remainder):
        print('Parsed JSON with extra tokens:', {'text': text, 'data': data, 'remainder': remainder})

    def parse(self, s):
        dbg and print(f'parse({s})')
        if len(s) >= 1:
            try:
                return json.loads(s)
            except json.JSONDecodeError as e:
                self._original_exception = e
                data, remainder = self.parse_any(s)
                self.last_parse_remainder = remainder
                if self.on_extra_token and remainder:
                    self.on_extra_token(s, data, remainder)
                return json.loads(json.dumps(data))
        else:
            return json.loads("{}")

    def parse_any(self, s):
        if not s:
            raise self._original_exception
        parser = self.get_parser(s)
        if not parser:
            raise self._original_exception
        return parser(s)

    def parse_space(self, s):
        # no effect on state
        r = self.parse_any(s.lstrip())
        self._pop('parse_space')
        return r

    def parse_array(self, s):
        array_complete = False

        s = s[1:]  # skip starting '['
        acc = []
        s = s.strip()
        while s:
            if s[0] == ']':
                s = s[1:]  # skip ending ']'
                array_complete = True
                break
            res, s = self.parse_any(s)
            acc.append(res)
            s = s.strip()
            if s.startswith(','):
                s = s[1:]
                s = s.strip()
        if array_complete:
            self._pop('parse_array')
        elif 0 < len(acc):
            self._path.insert(0, len(acc) - 1)
        return acc, s

    def parse_object(self, s):
        object_complete = False
        key_complete = False
        s = s[1:]  # skip starting '{'
        acc = {}
        s = s.strip()
        key = None
        while s:
            if s[0] == '}':
                s = s[1:]  # skip ending '}'
                object_complete = True
                break

            key_complete = False
            key, s = self.parse_any(s)
            s = s.strip()

            # Handle case where object ends after a key
            if not s or s[0] == '}':
                acc[key] = None
                break

            # Expecting a colon after the key
            if s[0] != ':':
                raise self._original_exception  # or handle this scenario as per your requirement

            key_complete = True
            s = s[1:]  # skip ':'
            s = s.strip()

            # Handle case where value is missing or incomplete
            if not s or s[0] in ',}':
                acc[key] = None
                if s.startswith(','):
                    s = s[1:]
                break

            value, s = self.parse_any(s)
            acc[key] = value
            s = s.strip()
            if s.startswith(','):
                s = s[1:]
                s = s.strip()
        if object_complete:
            self._pop('parse_object')
        elif key_complete:
            self._path.insert(0, key)
        return acc, s

    def parse_string(self, s):
        end = s.find('"', 1)
        while end != -1 and s[end - 1] == '\\':  # Handle escaped quotes
            end = s.find('"', end + 1)
        if end == -1:
            # Return the incomplete string without the opening quote
            return s[1:], ""
        str_val = s[:end + 1]
        s = s[end + 1:]
        str_val_unescaped = json.loads(str_val)
        self._pop('parse_string')
        return str_val_unescaped, s

    def parse_number(self, s):
        i = 0
        while i < len(s) and s[i] in '0123456789.-':
            i += 1
        num_str = s[:i]
        s = s[i:]
        if not num_str or num_str.endswith('.') or num_str.endswith('-'):
            return num_str, ""  # Return the incomplete number as is
        try:
            num = float(num_str) if '.' in num_str or 'e' in num_str or 'E' in num_str else int(num_str)
        except ValueError:
            raise self._original_exception
        self._pop('parse_number')
        return num, s

    def parse_true(self, s):
        if s.startswith('true'):
            self._pop('parse_true')
            return True, s[4:]
        raise self._original_exception

    def parse_false(self, s):
        if s.startswith('false'):
            self._pop('parse_false')
            return False, s[5:]
        raise self._original_exception

    def parse_null(self, s):
        if s.startswith('null'):
            self._pop('parse_null')
            return None, s[4:]
        raise self._original_exception
