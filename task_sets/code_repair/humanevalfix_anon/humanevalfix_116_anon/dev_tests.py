# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([1, 5, 2, 3, 4],), [1, 2, 4, 3, 5]),
    (([-2, -3, -4, -5, -6],), [-4, -2, -6, -5, -3]),
    (([1, 0, 2, 3, 4],), [0, 1, 2, 4, 3]),
    (([2, 5, 77, 4, 5, 3, 5, 7, 2, 3, 4],), [2, 2, 4, 4, 3, 3, 5, 5, 5, 7, 77]),
    (([2, 4, 8, 16, 32],), [2, 4, 8, 16, 32]),
]
