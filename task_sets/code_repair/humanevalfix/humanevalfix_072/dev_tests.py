# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([3, 2, 3], 9), True),
    (([1, 2], 5), False),
    (([3], 5), True),
    (([3, 2, 3], 1), False),
    (([1, 2, 3], 6), False),
]
