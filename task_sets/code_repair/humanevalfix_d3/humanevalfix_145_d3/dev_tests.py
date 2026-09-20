# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([1, 11, -1, -11, -12],), [-1, -11, 1, -12, 11]),
    (([],), []),
    (([1, -11, -32, 43, 54, -98, 2, -3],), [-3, -32, -98, -11, 1, 2, 43, 54]),
    (([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],), [1, 10, 2, 11, 3, 4, 5, 6, 7, 8, 9]),
]
