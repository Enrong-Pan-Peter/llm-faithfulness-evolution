# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([1, 2, 3, 4, 5, 6, 7], 4), 5),
    (([45, 2, 6, 8, 42, 90, 322], 1), 6),
    (([2, 6, 8, 3, 5, 7], 0), 2),
]
