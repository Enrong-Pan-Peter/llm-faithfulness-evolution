# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([1, 2, 2, -4],), -9),
    (([0, 1],), 0),
    (([],), None),
    (([1, 1, 1, 2, 3, -1, 1],), -10),
    (([-1, 1, -1, 1],), 4),
]
