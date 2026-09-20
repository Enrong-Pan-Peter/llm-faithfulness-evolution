# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (('Watashi', ['tEN', 'niNE', 'eIGHt8OKe']), 'Watashi.eIGHt8OKe'),
    (('__YESIMHERE', ['t', 'eMptY', 'nothing', 'zeR00', 'NuLl__', '123NoooneB321']), '__YESIMHERE.NuLl__'),
    (('__HAHA', ['Tab', '123', '781345', '-_-']), '__HAHA.123'),
    (('finNNalLLly', ['Die', 'NowW', 'Wow', 'WoW']), 'finNNalLLly.WoW'),
    (('Sp', ['671235', 'Bb']), 'Sp.671235'),
]
