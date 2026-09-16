# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    ((3,), [1, 2]),
    ((1,), [0, 1]),
    ((12,), [4, 6]),
    ((25,), [5, 6]),
]
