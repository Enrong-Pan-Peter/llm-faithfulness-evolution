# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([1, 2, 4, 20],), True),
    (([1, 20, 4, 10],), False),
    (([4, 1, 0, -10],), True),
    (([1, 2, 4, 10],), True),
    (([1, 2, 3, 2, 5, 60],), False),
    (([9, 9, 9, 9],), True),
]
