def solve(v1):
    v2 = {1: 'One', 2: 'Two', 3: 'Three', 4: 'Four', 5: 'Five', 6: 'Six', 7: 'Seven', 8: 'Eight', 9: 'Nine'}
    v3 = sorted(v1)
    v4 = []
    for v5 in v3:
        try:
            v4.append(v2[v5])
        except:
            pass
    return v4
