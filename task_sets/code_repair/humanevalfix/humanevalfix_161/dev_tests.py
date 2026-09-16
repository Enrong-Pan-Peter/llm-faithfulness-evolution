# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (('AsDf',), 'aSdF'),
    (('#a@C',), '#A@c'),
    (('#$a^D',), '#$A^d'),
    (('#6@2',), '2@6#'),
]
