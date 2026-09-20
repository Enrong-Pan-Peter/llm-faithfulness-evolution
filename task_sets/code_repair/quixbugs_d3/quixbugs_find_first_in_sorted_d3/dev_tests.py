# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([3, 4, 5, 5, 5, 5, 6], 5), 2),
    (([3, 4, 5, 5, 5, 5, 6], 7), -1),
    (([3, 6, 7, 9, 9, 10, 14, 27], 14), 6),
    (([0, 1, 6, 8, 13, 14, 67, 128], 67), 6),
]
