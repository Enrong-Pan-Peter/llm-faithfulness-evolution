# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([5, 8, 7, 1],), 12),
    (([3, 3, 3, 3, 3],), 9),
    (([30, 13, 24, 321],), 0),
    (([5, 9],), 5),
    (([3, 13, 2, 9],), 3),
]
