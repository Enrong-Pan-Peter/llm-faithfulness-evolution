# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    ((7,), [0, 1]),
    ((3452,), [2, 2]),
    ((-345821,), [3, 3]),
    ((0,), [1, 0]),
]
