# Hidden tests: (tuple of positional arguments, expected return value).
# Never shown to the model; these decide success.
TESTS = [
    ((4,), [2, 3]),
    ((20,), [2, 3, 5, 7, 11, 13, 17, 19]),
    ((1,), []),
]
