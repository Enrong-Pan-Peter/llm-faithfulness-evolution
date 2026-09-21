# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([4, 1, 5, 3, 7, 6, 2],), 3),
    (([10, 22, 9, 33, 21, 50, 41, 60, 80],), 6),
    (([9, 11, 2, 13, 7, 15],), 4),
    (([3],), 1),
    (([4, 2, 1],), 1),
    (([4, 1],), 1),
    (([0, 2],), 2),
]
