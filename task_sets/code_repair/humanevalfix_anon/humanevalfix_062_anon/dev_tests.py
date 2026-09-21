# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([3, 1, 2, 4, 5],), [1, 4, 12, 20]),
    (([1, 2, 3],), [2, 6]),
    (([3, 2, 1],), [2, 2]),
    (([1],), []),
]
