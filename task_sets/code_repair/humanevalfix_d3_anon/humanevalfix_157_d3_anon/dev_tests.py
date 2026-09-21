# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    ((3, 4, 5), True),
    ((1, 2, 3), False),
    ((10, 6, 8), True),
    ((7, 24, 25), True),
    ((5, 12, 13), True),
    ((48, 55, 73), True),
    ((2, 2, 10), False),
]
