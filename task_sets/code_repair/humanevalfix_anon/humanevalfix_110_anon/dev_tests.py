# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([1, 2, 3, 4], [1, 2, 3, 4]), 'YES'),
    (([1, 2, 3, 4], [1, 5, 3, 4]), 'NO'),
    (([1, 2, 3, 4], [2, 1, 4, 3]), 'YES'),
    (([100, 200], [200, 200]), 'YES'),
    (([3, 2, 6, 1, 8, 9], [3, 5, 5, 1, 1, 1]), 'NO'),
]
