# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([1, 3, 2],), 1),
    (([1, 3, 3, 2],), 0),
    (([],), 0),
    (([5],), 0),
    (([1, 2, 3, 4],), 0),
    (([2, 1, 2, 1, 2],), 1),
    (([1, 2, 2, 1],), 0),
]
