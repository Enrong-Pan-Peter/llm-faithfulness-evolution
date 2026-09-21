# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (('apple pi e',), True),
    (('eeeee',), False),
    (('Pumpkin pie 1',), False),
    (('eeeee e ',), False),
    (('apple pi e ',), False),
]
