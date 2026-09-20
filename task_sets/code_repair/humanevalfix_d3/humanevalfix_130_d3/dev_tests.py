# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    ((3,), [1, 3, 2.0, 8.0]),
    ((4,), [1, 3, 2.0, 8.0, 3.0]),
    ((1,), [1, 3]),
    ((5,), [1, 3, 2.0, 8.0, 3.0, 15.0]),
    ((7,), [1, 3, 2.0, 8.0, 3.0, 15.0, 4.0, 24.0]),
    ((9,), [1, 3, 2.0, 8.0, 3.0, 15.0, 4.0, 24.0, 5.0, 35.0]),
    ((2,), [1, 3, 2.0]),
]
