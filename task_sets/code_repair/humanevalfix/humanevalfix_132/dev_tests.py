# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (('[[]]',), True),
    (('[]]]]]]][[[[[]',), False),
    (('[][]',), False),
    (('[]',), False),
    (('[[]][[',), True),
    (('[[][]]',), True),
    (('[[[[]]]]',), True),
    (('[[]',), False),
    (('',), False),
    ((']]]]]]]]',), False),
]
