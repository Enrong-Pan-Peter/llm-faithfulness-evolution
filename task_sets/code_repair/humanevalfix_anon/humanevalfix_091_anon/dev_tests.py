# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (('I love It !',), 1),
    (('Is the sky blue?',), 0),
    (('You and I are going for a walk',), 0),
]
