# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    ((32,), 'db100000db'),
    ((15,), 'db1111db'),
    ((0,), 'db0db'),
]
