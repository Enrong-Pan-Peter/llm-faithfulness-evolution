# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    ((['1234567'],), ['the number of odd elements 4n the str4ng 4 of the 4nput.']),
    ((['3', '11111111'],), ['the number of odd elements 1n the str1ng 1 of the 1nput.', 'the number of odd elements 8n the str8ng 8 of the 8nput.']),
]
