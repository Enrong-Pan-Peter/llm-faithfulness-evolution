# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([2, 3, 4, 1, 2, 4],), 1),
    (([-1, -2, -3],), -6),
    (([-1, -2, -3, 2, -10],), -14),
    (([0, 10, 20, 1000000],), 0),
    (([100, -1, -2, -3, 10, -5],), -6),
    (([100, -33, 32, -1, 0, -2],), -33),
    (([7],), 7),
]
