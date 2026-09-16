# Hidden tests: (tuple of positional arguments, expected return value).
# Never shown to the model; these decide success.
TESTS = [
    (([1, 2, 3, [[4]]],), [1, 2, 3, 4]),
    ((['moe', 'curly', 'larry'],), ['moe', 'curly', 'larry']),
    (([[], [], [], [], []],), []),
]
