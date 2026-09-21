# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([10, '-', 5, '-', 2],), [10, 5, '-', 2, '-']),
    (([34, '-', 12, '/', 5],), [34, 12, 5, '/', '-']),
    (([4, '+', 9, '*', 9, '-', 10, '+', 13],), [4, 9, 9, '*', '+', 10, '-', 13, '+']),
    (([7, '*', 43, '-', 7, '+', 13, '/', 7],), [7, 43, '*', 7, '-', 13, 7, '/', '+']),
    (([30],), [30]),
]
