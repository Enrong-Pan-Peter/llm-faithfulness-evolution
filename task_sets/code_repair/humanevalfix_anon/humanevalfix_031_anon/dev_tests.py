# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    ((6,), False),
    ((101,), True),
    ((11,), True),
    ((13441,), True),
    ((61,), True),
    ((4,), False),
    ((1,), False),
    ((5,), True),
    ((77,), False),
]
