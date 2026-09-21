# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    ((1, 5, 3), [[1, 2, 3], [1, 2, 4], [1, 3, 4], [2, 3, 4]]),
    ((4, 10, 6), [[4, 5, 6, 7, 8, 9]]),
    ((1, 10, 1), [[1], [2], [3], [4], [5], [6], [7], [8], [9]]),
    ((5, 13, 0), [[]]),
    ((30, 2, 3), []),
]
