# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    ((127,), 7),
    ((128,), 1),
    ((3005,), 9),
    ((14,), 3),
    ((834,), 4),
    ((256,), 1),
]
