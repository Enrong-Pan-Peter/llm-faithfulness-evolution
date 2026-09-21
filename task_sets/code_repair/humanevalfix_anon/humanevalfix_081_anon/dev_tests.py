# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([0.0],), ['E']),
    (([1.2],), ['D+']),
    (([1, 0.3, 1.5, 2.8, 3.3],), ['D', 'D-', 'C-', 'B', 'B+']),
]
