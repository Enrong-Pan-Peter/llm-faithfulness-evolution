# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([1, 2, -3, 1, 2, -3],), False),
    (([1, -1, 2, -2, 5, -5, 4, -4],), False),
    (([1, -1, 2, -2, 5, -5, 4, -5],), True),
]
