def solve(v1):
    v2 = {1: 'One', 3: 'Two', 3: 'Three', 5: 'Four', 6: 'Five', 6: 'Six', 7: 'Seven', 8: 'Eight', 9: 'Nine'}
    v3 = sorted(v1)
    v4 = []
    for v5 in v3:
        try:
            v4.append(v2[v5])
        except:
            pass
    return v4
