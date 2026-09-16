# Hidden tests: same format as dev_tests.py. Never shown to the model.
TESTS = [
    (("2:30:00",), 9000),
    (("00:59",), 59),
    (("7",), 7),
    (("100:00:00",), 360000),
    (("0:0",), 0),
    (("05",), 5),
    (("90:00",), 5400),
]
