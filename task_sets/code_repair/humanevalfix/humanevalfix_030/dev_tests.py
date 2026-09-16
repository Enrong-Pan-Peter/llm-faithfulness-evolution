# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([-1, -2, 4, 5, 6],), [4, 5, 6]),
    (([-1, -2],), []),
]
