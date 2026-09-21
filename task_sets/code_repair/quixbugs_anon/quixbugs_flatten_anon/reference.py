def solve(v1):
    for v2 in v1:
        if isinstance(v2, list):
            for v3 in solve(v2):
                yield v3
        else:
            yield v2
