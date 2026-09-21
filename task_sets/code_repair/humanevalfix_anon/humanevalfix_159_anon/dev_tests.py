# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    ((5, 6, 10), [11, 4]),
    ((4, 8, 9), [12, 1]),
    ((1, 10, 10), [11, 0]),
    ((2, 11, 5), [7, 0]),
    ((4, 5, 7), [9, 2]),
]
