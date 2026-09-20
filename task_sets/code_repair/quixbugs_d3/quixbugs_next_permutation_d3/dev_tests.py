# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([3, 2, 4, 1],), [3, 4, 1, 2]),
    (([3, 5, 6, 2, 1],), [3, 6, 1, 2, 5]),
    (([4, 5, 1, 7, 9],), [4, 5, 1, 9, 7]),
    (([9, 5, 2, 6, 1],), [9, 5, 6, 1, 2]),
    (([3, 4, 5],), [3, 5, 4]),
]
