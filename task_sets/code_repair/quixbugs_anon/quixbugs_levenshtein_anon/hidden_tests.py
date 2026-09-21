# Hidden tests: (tuple of positional arguments, expected return value).
# Never shown to the model; these decide success.
TESTS = [
    (('kitten', 'sitting'), 3),
    (('abcdefg', 'gabcdef'), 2),
    (('', ''), 0),
]
