# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    ((1,), 2),
    ((2,), 3),
    ((3,), 5),
    ((4,), 13),
    ((5,), 89),
    ((6,), 233),
    ((8,), 28657),
    ((10,), 433494437),
]
