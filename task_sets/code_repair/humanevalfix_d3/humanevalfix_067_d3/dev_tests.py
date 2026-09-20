# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (('5 apples and 6 oranges', 19), 8),
    (('0 apples and 1 oranges', 3), 2),
    (('2 apples and 3 oranges', 100), 95),
    (('1 apples and 100 oranges', 120), 19),
]
