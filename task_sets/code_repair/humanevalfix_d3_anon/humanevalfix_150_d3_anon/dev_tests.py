# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    ((7, 34, 12), 34),
    ((15, 8, 5), 5),
    ((3, 33, 5212), 33),
    ((7919, -1, 12), -1),
    ((91, 56, 129), 129),
    ((1, 2, 0), 0),
]
