# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([],), 0),
    (([-1, -2, 0],), 0),
    (([1, 6, 9, -6, 0, 1, 5],), 5),
    (([0, 1],), 1),
]
