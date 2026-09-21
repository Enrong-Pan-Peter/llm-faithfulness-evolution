# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([4, -5, 2, 1, -1, 3],), 5),
    (([0, -1, 2, -1, 3, -1, 0],), 4),
    (([-2, 1, -3, 4, -1, 2, 1, -5, 4],), 6),
    (([-4, -4, -5],), 0),
]
