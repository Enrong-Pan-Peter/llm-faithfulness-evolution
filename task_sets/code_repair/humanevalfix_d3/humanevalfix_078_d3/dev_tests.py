# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (('AB',), 1),
    (('ABED1A33',), 4),
    (('123456789ABCDEF0',), 6),
    (([],), 0),
]
