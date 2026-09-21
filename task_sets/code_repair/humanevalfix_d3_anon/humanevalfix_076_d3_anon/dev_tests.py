# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    ((16, 2), True),
    ((4, 2), True),
    ((16, 4), True),
    ((128, 4), False),
    ((1, 1), True),
    ((1, 4), True),
]
