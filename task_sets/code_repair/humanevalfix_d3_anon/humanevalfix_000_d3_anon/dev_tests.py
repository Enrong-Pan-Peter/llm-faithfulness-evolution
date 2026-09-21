# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([1.0, 2.0, 3.9, 4.0, 5.0, 2.2], 0.05), False),
    (([1.1, 2.2, 3.1, 4.1, 5.1], 0.5), False),
    (([1.0, 2.0, 5.9, 4.0, 5.0], 0.95), True),
    (([1.1, 2.2, 3.1, 4.1, 5.1], 1.0), True),
]
