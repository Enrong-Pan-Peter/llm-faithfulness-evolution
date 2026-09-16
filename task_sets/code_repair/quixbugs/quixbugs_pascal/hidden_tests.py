# Hidden tests: (tuple of positional arguments, expected return value).
# Never shown to the model; these decide success.
TESTS = [
    ((3,), [[1], [1, 1], [1, 2, 1]]),
    ((1,), [[1]]),
]
