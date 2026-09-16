# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([1, 2, 3],), 14),
    (([1, 3, 5, 7],), 84),
    (([-2.4, 1, 1],), 6),
    (([10000, 10000],), 200000000),
    (([-1.4, 17.9, 18.9, 19.9],), 1086),
    (([-1, 1, 0],), 2),
]
