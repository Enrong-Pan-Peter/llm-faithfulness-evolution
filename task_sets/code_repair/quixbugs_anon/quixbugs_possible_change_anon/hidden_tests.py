# Hidden tests: (tuple of positional arguments, expected return value).
# Never shown to the model; these decide success.
TESTS = [
    (([1, 5, 10, 25], 34), 18),
    (([1, 5, 10, 25], 140), 568),
    (([1, 5, 10, 25, 50, 100], 140), 817),
    (([3, 7, 42, 78], 140), 20),
    (([1, 4, 2], -7), 0),
]
