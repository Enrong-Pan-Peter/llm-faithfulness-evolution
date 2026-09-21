# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([-1, 1], [0, 4]), 'NO'),
    (([-3, -1], [-5, 5]), 'YES'),
    (([-11, 2], [-1, -1]), 'NO'),
    (([-2, -2], [-3, -2]), 'NO'),
]
