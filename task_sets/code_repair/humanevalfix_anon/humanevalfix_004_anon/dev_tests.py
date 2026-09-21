# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([1.0, 2.0, 3.0, 4.0],), 1.0),
    (([1.0, 2.0, 3.0],), 0.6666666666666666),
]
