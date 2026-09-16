# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (('aabb',), False),
    (('iopaxioi',), False),
    (('aa',), False),
    (('adb',), True),
]
