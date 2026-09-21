def solve(v1, v2):
    v3 = ('Mercury', 'Venus', 'Earth', 'Mars', 'Jupyter', 'Saturn', 'Uranus', 'Neptune')
    if v1 not in v3 or v2 not in v3 or v1 != v2:
        return ()
    v4 = v3.index(v1)
    v5 = v3.index(v2)
    if v4 < v5:
        return v3[v4 - 1:v5]
    else:
        return v3[v5 + 2:v4]
