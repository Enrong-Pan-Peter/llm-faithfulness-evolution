# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (('Hi',), 'Hi'),
    (('hello',), 'ehllo'),
    (('Hello World!!!',), 'Hello !!!Wdlor'),
    (('Hi. My name is Mister Robot. How are you?',), '.Hi My aemn is Meirst .Rboot How aer ?ouy'),
    (('abcd',), 'abcd'),
]
