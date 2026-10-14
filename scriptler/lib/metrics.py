"""Shared source-boundary matching and segmentation metrics."""
import re
import numpy as np


def match_boundaries(expected, predicted, tolerance):
    expected,predicted=sorted(set(expected)),sorted(set(predicted))
    table={}
    for i in range(len(expected)+1):
        for j in range(len(predicted)+1):
            if not i or not j:
                table[i,j]=(0,0,[]); continue
            options=[table[i-1,j],table[i,j-1]]
            distance=abs(expected[i-1]-predicted[j-1])
            if distance<=tolerance:
                count,total,pairs=table[i-1,j-1]
                options.append((count+1,total+distance,pairs+[(expected[i-1],predicted[j-1],distance)]))
            table[i,j]=max(options,key=lambda x:(x[0],-x[1]))
    matches=[{'reference':a,'prediction':b,'distance_chars':d} for a,b,d in table[len(expected),len(predicted)][2]]
    used_a={m['reference'] for m in matches}; used_b={m['prediction'] for m in matches}
    tp=len(matches); fp=len(predicted)-tp; fn=len(expected)-tp
    return {'tp':tp,'fp':fp,'fn':fn,'precision':tp/(tp+fp) if tp+fp else None,
            'recall':tp/(tp+fn) if tp+fn else None,'f1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,
            'matches':matches,'missed':sorted(set(expected)-used_a),'extra':sorted(set(predicted)-used_b)}


def metrics(data, expected, cuts):
    result = {'exact': match_boundaries(expected, cuts, 0), 'within_80_chars': match_boundaries(expected, cuts, 80)}
    spans = list(re.finditer(r'\S+', data['text']))
    positions = [s.start() for s in spans]
    reference = np.searchsorted(positions, expected)
    prediction = np.searchsorted(positions, cuts)
    n = len(spans)
    k = max(1, round(n / (2 * (len(expected) + 1))))
    if n <= k:
        result.update(pk=None, windowdiff=None)
    else:
        left = np.arange(n - k)
        right = left + k
        r = np.searchsorted(reference, right, side='right') - np.searchsorted(reference, left, side='right')
        p = np.searchsorted(prediction, right, side='right') - np.searchsorted(prediction, left, side='right')
        result.update(pk=float(np.mean((r > 0) != (p > 0))), windowdiff=float(np.mean(r != p)))
    a = [0] + expected + [len(data['text'])]
    b = [0] + cuts + [len(data['text'])]
    def coverage(first, second):
        return sum(max(max(0, min(y, v) - max(x, u)) for u, v in zip(second, second[1:]))
                   for x, y in zip(first, first[1:])) / len(data['text'])
    result.update(purity=coverage(b, a), coverage=coverage(a, b), cut_count=len(cuts))
    return result
