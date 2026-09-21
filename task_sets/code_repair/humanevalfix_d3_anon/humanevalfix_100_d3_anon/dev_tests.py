# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    ((3,), [3, 5, 7]),
    ((4,), [4, 6, 8, 10]),
    ((6,), [6, 8, 10, 12, 14, 16]),
]
