# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    ((3, 5), 3),
    ((1101, 101), 2),
    ((0, 101), 1),
    ((3, 11), 8),
    ((100, 101), 1),
    ((30, 5), 4),
]
