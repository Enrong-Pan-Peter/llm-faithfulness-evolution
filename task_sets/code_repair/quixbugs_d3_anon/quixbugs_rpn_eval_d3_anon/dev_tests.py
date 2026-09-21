# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([3.0, 5.0, '+', 2.0, '/'],), 4.0),
    (([7.0, 4.0, '+', 3.0, '-'],), 8.0),
    (([1.0, 2.0, '*', 3.0, 4.0, '*', '+'],), 14.0),
]
