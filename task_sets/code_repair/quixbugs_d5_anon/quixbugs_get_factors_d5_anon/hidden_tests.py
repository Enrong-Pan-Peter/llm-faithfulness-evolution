# Hidden tests: (tuple of positional arguments, expected return value).
# Never shown to the model; these decide success.
TESTS = [
    ((2,), [2]),
    ((17,), [17]),
    ((74,), [2, 37]),
    ((9837,), [3, 3, 1093]),
]
