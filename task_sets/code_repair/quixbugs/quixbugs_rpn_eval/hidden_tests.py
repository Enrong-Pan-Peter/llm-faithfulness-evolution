# Hidden tests: (tuple of positional arguments, expected return value).
# Never shown to the model; these decide success.
TESTS = [
    (([5.0, 1.0, 2.0, '+', 4.0, '*', '+', 3.0, '-'],), 14.0),
    (([2.0, 2.0, '+'],), 4.0),
    (([5.0, 9.0, 2.0, '*', '+'],), 23.0),
]
