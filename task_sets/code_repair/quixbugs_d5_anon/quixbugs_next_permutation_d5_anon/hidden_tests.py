# Hidden tests: (tuple of positional arguments, expected return value).
# Never shown to the model; these decide success.
TESTS = [
    (([3, 5, 6, 2],), [3, 6, 2, 5]),
    (([4, 5, 8, 7, 1],), [4, 7, 1, 5, 8]),
    (([44, 5, 1, 7, 9],), [44, 5, 1, 9, 7]),
]
