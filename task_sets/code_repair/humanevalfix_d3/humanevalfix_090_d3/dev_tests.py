# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([1, 2, 3, 4, 5],), 2),
    (([5, 1, 4, 3, 2],), 2),
    (([],), None),
    (([1, 1],), None),
    (([1, 1, 1, 1, 0],), 1),
]
