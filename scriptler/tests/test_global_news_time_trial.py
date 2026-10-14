import itertools
from pathlib import Path
import tempfile
import unittest

import numpy as np

from scriptler.denemeler.yerel.global_news_time_trial import ROOT, decode, export, metrics, source_axis


class GlobalNewsTimeTests(unittest.TestCase):
    def document(self):
        return {'data': {'text': 'aa bb cc dd', 'units': []}, 'positions': np.array([0, 3, 6, 9, 11]),
                'logits': np.array([0., -.5, 2., -.5, 0.]),
                'coherence': np.array([[0, 0, 0, 1, 2], [0, 0, 0, 1, 1], [0, 0, 0, 0, 0],
                                       [0, 0, 0, 0, 0], [0, 0, 0, 0, 0]], dtype=float)}

    def test_global_optimum_against_exhaustive_partitions(self):
        d = self.document()
        duration = np.array([[0, 1, 0, .5, 1], [0, 0, 1, 0, .5], [0, 0, 0, 1, 0],
                             [0, 0, 0, 0, 1], [0, 0, 0, 0, 0]], dtype=float)
        settings = {'penalty': .7, 'duration_weight': .4, 'coherence_weight': .8}
        best = (-float('inf'), None)
        for bits in itertools.product([False, True], repeat=3):
            internal = [i + 1 for i, b in enumerate(bits) if b]
            starts, ends = [0] + internal, internal + [4]
            value = sum((d['logits'][a] - .7 if a else 0) - .4 * duration[a, b]
                        - .8 * d['coherence'][a, b] for a, b in zip(starts, ends))
            if value > best[0]:
                best = value, internal
        cuts, score = decode(d, duration, settings)
        self.assertAlmostEqual(score, best[0])
        self.assertEqual(cuts, [int(d['positions'][i]) for i in best[1]])

    def test_partition_metrics_detect_excessive_splitting_and_merging(self):
        text = ' '.join('w' + str(i) for i in range(30))
        import re
        positions = [m.start() for m in re.finditer(r'\S+', text)]
        expected = [positions[15]]
        perfect = metrics({'text': text}, expected, expected)
        fragmented = metrics({'text': text}, expected, positions[1:])
        merged = metrics({'text': text}, expected, [])
        self.assertEqual(perfect['windowdiff'], 0)
        self.assertEqual(perfect['purity'], 1)
        self.assertEqual(perfect['coverage'], 1)
        self.assertLess(fragmented['coverage'], 1)
        self.assertLess(merged['purity'], 1)
        self.assertGreater(fragmented['windowdiff'], 0)

    def test_export_preserves_original_bytes_and_refuses_overwrite(self):
        d = self.document()
        with tempfile.TemporaryDirectory(dir=ROOT / 'work') as temp:
            folder = Path(temp) / 'out'
            export(d, [6], folder, 'frozen', 1.)
            self.assertEqual(b''.join(p.read_bytes() for p in sorted(folder.glob('taslak*.txt'))), d['data']['text'].encode())
            with self.assertRaises(ValueError):
                export(d, [6], folder, 'frozen', 1.)

    def test_cue_internal_times_are_monotonic_and_explicitly_interpolated(self):
        data = {'text': 'aa bb cc dd', 'units': [
            {'start_char': 0, 'start_seconds': 0, 'end_seconds': 2},
            {'start_char': 6, 'start_seconds': 3, 'end_seconds': 5}]}
        _, positions, times = source_axis(data)
        self.assertEqual(list(positions), [0, 3, 6, 9, 11])
        self.assertEqual(list(times), [0., 1., 3., 4., 5.])


if __name__ == '__main__':
    unittest.main()
