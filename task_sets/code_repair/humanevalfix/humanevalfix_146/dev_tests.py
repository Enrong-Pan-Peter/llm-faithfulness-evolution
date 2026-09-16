# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([15, -73, 14, -15],), 1),
    (([33, -2, -3, 45, 21, 109],), 2),
    (([71, -2, -33, 75, 21, 19],), 3),
    (([43, -12, 93, 125, 121, 109],), 4),
    (([],), 0),
]
