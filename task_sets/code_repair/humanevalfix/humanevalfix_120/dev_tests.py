# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([-3, -4, 5], 3), [-4, -3, 5]),
    (([-3, 2, 1, 2, -1, -2, 1], 1), [2]),
    (([-123, 20, 0, 1, 2, -3], 4), [0, 1, 2, 20]),
    (([-1, 0, 2, 5, 3, -10], 2), [3, 5]),
    (([4, -4], 2), [-4, 4]),
]
