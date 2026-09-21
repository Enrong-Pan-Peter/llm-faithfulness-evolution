# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([1, 2, 3],), 6),
    (([-1, -5, 2, -1, -5],), -126),
    (([-16, -9, -2, 36, 36, 26, -20, 25, -40, 20, -4, 12, -26, 35, 37],), -14196),
    (([1, 1, 1, 1, 1, 1, 1, 1, 1],), 9),
    (([0],), 0),
]
