# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([1.0, 2.0, 3.0, 4.0, 5.0],), [0.0, 0.25, 0.5, 0.75, 1.0]),
    (([2.0, 49.9],), [0.0, 1.0]),
    (([2.0, 1.0, 5.0, 3.0, 4.0],), [0.25, 0.0, 1.0, 0.5, 0.75]),
]
