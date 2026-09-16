# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    ((12, 2), '12'),
    ((12, 1), '21'),
    ((100, 2), '001'),
    ((11, 101), '11'),
]
