# Hidden tests: (tuple of positional arguments, expected return value).
# Never shown to the model; these decide success.
TESTS = [
    (([7, 10, 9, 2, 3, 8, 1],), 3),
    (([],), 0),
    (([10, 20, 11, 32, 22, 48, 43],), 4),
    (([5, 1, 3, 4, 7],), 4),
    (([-1, 0, 2],), 3),
]
