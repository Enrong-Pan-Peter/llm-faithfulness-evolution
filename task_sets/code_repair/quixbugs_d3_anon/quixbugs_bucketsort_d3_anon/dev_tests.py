# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([3, 11, 2, 9, 1, 5], 12), [1, 2, 3, 5, 9, 11]),
    (([1, 3, 4, 6, 4, 2, 9, 1, 2, 9], 10), [1, 1, 2, 2, 3, 4, 4, 6, 9, 9]),
    (([20, 21, 22, 23, 24, 25, 26, 27, 28, 29], 30), [20, 21, 22, 23, 24, 25, 26, 27, 28, 29]),
]
