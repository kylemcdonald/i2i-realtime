from itertools import islice
from itertools import chain

def chunks(x, n):
    # return slices of lists
    if hasattr(x, '__len__'):
        for i in range(0, len(x), n):
            yield x[i:i+n]
    else:
        # return sub-generators of generators
        i = iter(x)
        for e in i:
            yield chain([e], islice(i, n-1))