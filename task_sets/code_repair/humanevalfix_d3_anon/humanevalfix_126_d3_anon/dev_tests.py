# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([5],), True),
    (([1, 2, 3, 4, 5],), True),
    (([1, 3, 2, 4, 5],), False),
    (([1, 2, 3, 4, 5, 6],), True),
    (([1, 2, 3, 4, 5, 6, 7],), True),
    (([1, 3, 2, 4, 5, 6, 7],), False),
    (([1, 2, 2, 2, 3, 4],), False),
    (([1, 2, 2, 3, 3, 4],), True),
    (([1, 2, 3, 3, 3, 4],), False),
    (([1],), True),
    (([1, 2, 3, 4],), True),
]
