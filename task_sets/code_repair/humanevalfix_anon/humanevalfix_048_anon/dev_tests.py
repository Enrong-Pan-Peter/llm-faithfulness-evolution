# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (('',), True),
    (('aba',), True),
    (('aaaaa',), True),
    (('zbcd',), False),
    (('xywyx',), True),
    (('xywzx',), False),
]
