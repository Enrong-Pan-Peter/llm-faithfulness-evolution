# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    ((8, 3), '22'),
    ((8, 2), '1000'),
    ((7, 2), '111'),
    ((9, 3), '100'),
    ((16, 2), '10000'),
    ((3, 4), '3'),
    ((5, 6), '5'),
    ((7, 8), '7'),
]
