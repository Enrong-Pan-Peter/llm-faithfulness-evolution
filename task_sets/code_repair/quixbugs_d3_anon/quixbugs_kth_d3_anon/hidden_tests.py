# Hidden tests: (tuple of positional arguments, expected return value).
# Never shown to the model; these decide success.
TESTS = [
    (([3, 6, 7, 1, 6, 3, 8, 9], 5), 7),
    (([45, 2, 6, 8, 42, 90, 322], 6), 322),
    (([3, 6, 7, 1, 6, 3, 8, 9], 2), 3),
    (([34, 25, 7, 1, 9], 4), 34),
]
