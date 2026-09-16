# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (('a b b a',), {'a': 2, 'b': 2}),
    (('a b c a b',), {'a': 2, 'b': 2}),
    (('b b b b a',), {'b': 4}),
    (('',), {}),
    (('r t g',), {'r': 1, 't': 1, 'g': 1}),
]
