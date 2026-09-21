# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (('efef', 'fee'), True),
    (('yello', 'ell'), True),
    (('abab', 'aabb'), False),
]
