# Hidden tests: (tuple of positional arguments, expected return value).
# Never shown to the model; these decide success.
TESTS = [
    (([24, 26, 28, 50, 59], 101), -1),
    (([1, 2, 3, 4, 6, 7, 8], 4), 3),
    (([3, 5, 6, 7, 8, 9, 12, 13, 14, 24, 26, 27], 0), -1),
]
