# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    ((30,), True),
    ((5,), False),
    ((10,), False),
]
