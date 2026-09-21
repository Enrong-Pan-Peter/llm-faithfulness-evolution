# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (('03-11-2000',), True),
    (('15-01-2012',), False),
    (('04-0-2040',), False),
    (('06-04-2020',), True),
    (('03-32-2011',), False),
    (('04-31-3000',), False),
    (('21-31-2000',), False),
    (('04122003',), False),
    (('2003-04',), False),
    (('04-2003',), False),
]
