# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (('aBCdEf',), 1),
    (('abcdefg',), 0),
    (('dBBE',), 0),
    (('U',), 1),
    (('',), 0),
]
