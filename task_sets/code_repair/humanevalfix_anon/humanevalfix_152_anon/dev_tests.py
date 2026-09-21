# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([1, 2, 3, 4, 5, 1], [1, 2, 3, 4, 2, -2]), [0, 0, 0, 0, 3, 3]),
    (([1, 2, 3, 5], [-1, 2, 3, 4]), [2, 0, 0, 1]),
]
