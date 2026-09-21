# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    ((50,), 0),
    ((78,), 2),
    ((79,), 3),
    ((100,), 3),
    ((4000,), 192),
    ((100000,), 8026),
]
