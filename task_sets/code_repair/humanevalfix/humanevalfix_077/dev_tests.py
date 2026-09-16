# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    ((1,), True),
    ((2,), False),
    ((-1,), True),
    ((64,), True),
    ((180,), False),
    ((0,), True),
    ((1000,), True),
]
