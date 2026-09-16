# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    ((5,), [2, 3]),
    ((0,), []),
    ((1,), []),
    ((18,), [2, 3, 5, 7, 11, 13, 17]),
    ((6,), [2, 3, 5]),
    ((10,), [2, 3, 5, 7]),
    ((47,), [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43]),
]
