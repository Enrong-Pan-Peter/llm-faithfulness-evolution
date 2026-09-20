# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([2, 4, 1, 3, 5, 7],), [None, 1]),
    (([],), [None, None]),
    (([0],), [None, None]),
    (([2, 4, 1, 3, 5, 7, 0],), [None, 1]),
    (([4, 5, 3, 6, 2, 7, -7],), [-7, 2]),
    (([-1, -3, -5, -6],), [-1, None]),
    (([-6, -4, -4, -3, 1],), [-3, 1]),
]
