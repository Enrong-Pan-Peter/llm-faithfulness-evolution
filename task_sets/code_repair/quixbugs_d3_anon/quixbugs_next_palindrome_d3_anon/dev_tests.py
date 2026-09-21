# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([9, 9, 9],), [1, 0, 0, 1]),
    (([1, 3, 1],), [1, 4, 1]),
    (([4, 7, 2, 5, 2, 7, 4],), [4, 7, 2, 6, 2, 7, 4]),
]
