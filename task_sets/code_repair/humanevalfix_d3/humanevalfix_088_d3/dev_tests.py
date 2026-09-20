# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([],), []),
    (([5],), [5]),
    (([2, 4, 3, 0, 1, 5],), [0, 1, 2, 3, 4, 5]),
    (([2, 4, 3, 0, 1, 5, 6],), [6, 5, 4, 3, 2, 1, 0]),
    (([2, 1],), [1, 2]),
    (([21, 14, 23, 11],), [23, 21, 14, 11]),
]
