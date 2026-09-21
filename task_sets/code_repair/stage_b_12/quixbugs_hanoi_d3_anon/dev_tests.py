# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    ((1, 1, 3), [[1, 3]]),
    ((3, 1, 3), [[1, 3], [1, 2], [3, 2], [1, 3], [2, 1], [2, 3], [1, 3]]),
    ((2, 1, 2), [[1, 3], [1, 2], [3, 2]]),
    ((2, 3, 1), [[3, 2], [3, 1], [2, 1]]),
]
