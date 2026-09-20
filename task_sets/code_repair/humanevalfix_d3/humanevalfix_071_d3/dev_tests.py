# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    ((3, 4, 5), 6.0),
    ((1, 2, 10), -1),
    ((4, 8, 5), 8.18),
    ((10, 5, 7), 16.25),
    ((2, 6, 3), -1),
]
