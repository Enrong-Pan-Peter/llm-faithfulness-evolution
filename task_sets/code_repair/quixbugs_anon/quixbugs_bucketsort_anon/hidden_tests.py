# Hidden tests: (tuple of positional arguments, expected return value).
# Never shown to the model; these decide success.
TESTS = [
    (([3, 2, 4, 2, 3, 5], 6), [2, 2, 3, 3, 4, 5]),
    (([20, 19, 18, 17, 16, 15, 14, 13, 12, 11], 21), [11, 12, 13, 14, 15, 16, 17, 18, 19, 20]),
    (([8, 5, 3, 1, 9, 6, 0, 7, 4, 2, 5], 10), [0, 1, 2, 3, 4, 5, 5, 6, 7, 8, 9]),
    (([], 14), []),
]
