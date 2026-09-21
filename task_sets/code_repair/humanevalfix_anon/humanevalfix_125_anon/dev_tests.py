# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (('Hello,world!',), ['Hello', 'world!']),
    (('Hello world,!',), ['Hello', 'world,!']),
    (('abcdef',), 3),
    (('aaaBb',), 1),
]
