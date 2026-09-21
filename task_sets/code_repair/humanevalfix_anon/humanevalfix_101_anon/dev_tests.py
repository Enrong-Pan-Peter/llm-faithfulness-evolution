# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (('Hi, my name is John',), ['Hi', 'my', 'name', 'is', 'John']),
    (('Hi, my name',), ['Hi', 'my', 'name']),
    (('ahmed     , gamal',), ['ahmed', 'gamal']),
]
