# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([3, 4, 5, 1, 2],), True),
    (([3, 5, 4, 1, 2],), False),
    (([3, 5, 10, 1, 2],), True),
    (([],), True),
]
