# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([1, 2, 3, 4],), [1, 4, 2, 3]),
    (([5, 5, 5, 5],), [5, 5, 5, 5]),
    (([],), []),
    (([5, 6, 7, 8, 9],), [5, 9, 6, 8, 7]),
    (([5, 6, 7, 8, 9, 1],), [1, 9, 5, 8, 6, 7]),
    (([0, 2, 2, 2, 5, 5, -5, -5],), [-5, 5, -5, 5, 0, 2, 2, 2]),
]
