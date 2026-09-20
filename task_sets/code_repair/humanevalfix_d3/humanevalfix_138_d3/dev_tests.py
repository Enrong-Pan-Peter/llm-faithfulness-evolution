# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    ((4,), False),
    ((6,), False),
    ((8,), True),
    ((10,), True),
    ((16,), True),
    ((13,), False),
]
