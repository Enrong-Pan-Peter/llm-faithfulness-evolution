# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    ((5,), [[1], [1, 1], [1, 2, 1], [1, 3, 3, 1], [1, 4, 6, 4, 1]]),
    ((2,), [[1], [1, 1]]),
    ((4,), [[1], [1, 1], [1, 2, 1], [1, 3, 3, 1]]),
]
