# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([4, 2, 3],), [2, 1]),
    (([5, 0, 3, 0, 4, 2],), [0, 1]),
    (([5, 4, 8, 4, 8],), [4, 1]),
    (([7, 9, 7, 1],), []),
]
