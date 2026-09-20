# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (('o o o o',), [4, 4, 4, 4]),
    (('o| .| o| .| o o| o o|',), [2, 1, 2, 1, 4, 2, 4, 2]),
    (('.| .| .| .|',), [1, 1, 1, 1]),
]
