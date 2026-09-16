# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([1, 2, 3],), [1, 2, 3]),
    (([5, 3, -5, 2, -3, 3, 9, 0, 123, 1, -10],), [-10, 3, -5, 2, -3, 3, 5, 0, 9, 1, 123]),
]
