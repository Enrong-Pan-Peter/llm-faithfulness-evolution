# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (('7/10', '10/2'), False),
    (('1/6', '2/1'), False),
    (('2/10', '50/10'), True),
    (('11/6', '6/1'), True),
    (('5/2', '3/5'), False),
    (('2/4', '4/2'), True),
]
