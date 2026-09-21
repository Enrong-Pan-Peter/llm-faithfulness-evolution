# Hidden tests: (tuple of positional arguments, expected return value).
# Never shown to the model; these decide success.
TESTS = [
    (('abcbdab', 'bdcaba'), 'bcba'),
    (('ABCBDAB', 'BDCABA'), 'BCBA'),
    (('daenarys', 'targaryen'), 'aary'),
    (('1234', '1224533324'), '1234'),
    (('acbdegcedbg', 'begcfeubk'), 'begceb'),
]
