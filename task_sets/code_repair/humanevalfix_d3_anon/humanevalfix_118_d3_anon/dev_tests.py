# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (('easy',), ''),
    (('ali',), ''),
    (('ba',), ''),
    (('Asia',), ''),
    (('full',), 'u'),
    (('most',), 'o'),
    (('Above',), 'o'),
]
