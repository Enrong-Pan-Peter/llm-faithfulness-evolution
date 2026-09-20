# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    ((2, 3, 1), True),
    ((1.5, 5, 3.5), False),
    ((4, 2, 2), True),
    ((-4, 6, 2), True),
    ((3, 4, 7), True),
]
