# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (('Jupiter', 'Neptune'), ['Saturn', 'Uranus']),
    (('Neptune', 'Venus'), ['Earth', 'Mars', 'Jupiter', 'Saturn', 'Uranus']),
    (('Earth', 'Earth'), []),
    (('Jupiter', 'Makemake'), []),
]
