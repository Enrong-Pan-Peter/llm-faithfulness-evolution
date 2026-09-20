# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    ((8,), [2, 2, 2]),
    ((2,), [2]),
    ((57,), [3, 19]),
    ((185193,), [3, 3, 3, 19, 19, 19]),
    ((18,), [2, 3, 3]),
]
