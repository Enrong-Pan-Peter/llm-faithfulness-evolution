# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([1, 3, 5, 0],), False),
    (([1, 3, -2, 1],), False),
    (([1, 2, 3, 7],), False),
    (([2, 4, -5, 3, 5, 7],), True),
    (([1],), False),
    (([-3, 9, -1, 3, 2, 31],), True),
    (([-3, 9, -1, 4, 2, 31],), False),
]
