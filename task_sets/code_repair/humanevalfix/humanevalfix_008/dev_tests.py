# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([],), [0, 1]),
    (([1, 1, 1],), [3, 1]),
    (([10],), [10, 10]),
]
