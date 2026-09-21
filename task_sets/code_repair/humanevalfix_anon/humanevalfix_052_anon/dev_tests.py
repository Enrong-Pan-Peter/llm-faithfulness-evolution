# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([1, 2, 4, 10], 100), True),
    (([1, 20, 4, 10], 5), False),
    (([1, 20, 4, 10], 21), True),
    (([1, 8, 4, 10], 11), True),
]
