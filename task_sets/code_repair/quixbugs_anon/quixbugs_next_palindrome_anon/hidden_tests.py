# Hidden tests: (tuple of positional arguments, expected return value).
# Never shown to the model; these decide success.
TESTS = [
    (([1, 4, 9, 4, 1],), [1, 5, 0, 5, 1]),
    (([4, 7, 2, 5, 5, 2, 7, 4],), [4, 7, 2, 6, 6, 2, 7, 4]),
]
