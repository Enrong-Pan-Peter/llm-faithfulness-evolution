# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    ((12, 15), 14),
    ((13, 12), -1),
    ((6, 29), 28),
    ((5234, 5233), -1),
    ((7, 7), -1),
]
