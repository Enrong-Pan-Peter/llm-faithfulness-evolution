# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (('Hello',), True),
    (('abcdcba',), True),
    (('kittens',), True),
    (('orange',), False),
    (('gogo',), False),
    (('world',), True),
    (('Wow',), True),
    (('HI',), True),
    (('aaaaaaaaaaaaaaa',), False),
    (('M',), False),
]
