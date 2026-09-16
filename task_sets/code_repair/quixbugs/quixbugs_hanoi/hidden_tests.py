# Hidden tests: (tuple of positional arguments, expected return value).
# Never shown to the model; these decide success.
TESTS = [
    ((2, 1, 3), [[1, 2], [1, 3], [2, 3]]),
    ((4, 1, 3), [[1, 2], [1, 3], [2, 3], [1, 2], [3, 1], [3, 2], [1, 2], [1, 3], [2, 3], [2, 1], [3, 1], [2, 3], [1, 2], [1, 3], [2, 3]]),
    ((2, 1, 1), [[1, 2], [1, 1], [2, 1]]),
    ((0, 1, 3), []),
]
