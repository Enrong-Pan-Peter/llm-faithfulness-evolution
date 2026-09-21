# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([1, 2, 3, 4, 3, 2, 2],), 1),
    (([1, 2, 3, 2, 1],), 0),
    (([1, 4, 4, 2],), 1),
    (([1, 4, 2],), 1),
    (([0, 1],), 1),
]
