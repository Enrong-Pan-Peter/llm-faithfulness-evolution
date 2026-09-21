# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    ((2,), 1),
    ((1,), 0),
    ((5,), 4),
    ((8,), 24),
    ((10,), 81),
    ((14,), 927),
]
