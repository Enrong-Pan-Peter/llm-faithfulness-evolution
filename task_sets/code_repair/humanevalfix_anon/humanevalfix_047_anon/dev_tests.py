# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([3, 1, 2, 4, 5],), 3),
    (([-10, 4, 6, 1000, 10, 20],), 8.0),
    (([6, 5],), 5.5),
    (([8, 1, 3, 9, 9, 2, 7],), 7),
]
