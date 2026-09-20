# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([3, 4, 5, 5, 5, 5, 6], 5), 3),
    (([1, 2, 3, 4, 6, 7, 8], 5), -1),
    (([2, 4, 6, 8, 10, 12, 14, 16, 18, 20], 18), 8),
    (([3, 5, 6, 7, 8, 9, 12, 12, 14, 24, 26, 27], 12), 6),
]
