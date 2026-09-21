# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([1, 5, 10, 25], 11), 4),
    (([1, 5, 10, 25], 75), 121),
    (([1, 5, 10], 34), 16),
    (([1, 5, 10, 25, 50], 140), 786),
    (([1, 3, 7, 42, 78], 140), 981),
]
