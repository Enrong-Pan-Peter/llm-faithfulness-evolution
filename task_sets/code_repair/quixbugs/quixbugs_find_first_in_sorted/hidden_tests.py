# Hidden tests: (tuple of positional arguments, expected return value).
# Never shown to the model; these decide success.
TESTS = [
    (([3, 4, 5, 5, 5, 5, 6], 2), -1),
    (([0, 1, 6, 8, 13, 14, 67, 128], 80), -1),
    (([0, 1, 6, 8, 13, 14, 67, 128], 128), 7),
]
