# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([1, 4, 3, 34, 653, 2, 5], [5, 7, 1, 5, 9, 653, 121]), [1, 5, 653]),
    (([5, 3, 2, 8], [3, 2]), [2, 3]),
    (([4, 3, 2, 8], [3, 2, 4]), [2, 3, 4]),
]
