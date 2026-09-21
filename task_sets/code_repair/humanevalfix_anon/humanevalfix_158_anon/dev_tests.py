# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    ((['name', 'of', 'string'],), 'string'),
    ((['we', 'are', 'a', 'mad', 'nation'],), 'nation'),
    ((['aaaaaaa', 'bb', 'cc'],), 'aaaaaaa'),
    ((['play', 'this', 'game', 'of', 'footbott'],), 'footbott'),
    ((['play', 'play', 'play'],), 'play'),
]
