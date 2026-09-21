# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([4, 5, 6, 7, 2, 122],), 122),
    (([4, 4, 6, 8],), 12),
]
