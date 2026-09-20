# Hidden tests: (tuple of positional arguments, expected return value).
# Never shown to the model; these decide success.
TESTS = [
    (('cyborg', 'cyber'), 3),
    (('space age', 'pace a'), 6),
    (('acbdegcedbg', 'begcfeubk'), 3),
    (('fun', ''), 0),
]
