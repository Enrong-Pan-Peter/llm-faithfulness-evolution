# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (('(()()) ((())) () ((())()())',), [2, 3, 1, 3]),
    (('() (()) ((())) (((())))',), [1, 2, 3, 4]),
]
