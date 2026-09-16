# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    ((1, 2.5), 2.5),
    (('5,1', '6'), '6'),
    ((2, 3), 3),
    ((1, '2,3'), '2,3'),
    (('1', 1), None),
]
