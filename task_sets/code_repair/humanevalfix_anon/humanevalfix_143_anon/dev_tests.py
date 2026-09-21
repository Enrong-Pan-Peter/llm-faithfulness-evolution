# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (('This is a test',), 'is'),
    (('there is no place available here',), 'there is no place'),
    (('here',), ''),
]
