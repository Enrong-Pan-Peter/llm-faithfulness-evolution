# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (('Mary had a little lamb', 4), ['little']),
    (('simple white space', 2), []),
    (('Uncle sam', 3), ['Uncle']),
]
