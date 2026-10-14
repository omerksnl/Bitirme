import unittest
from scriptler.lib.metrics import match_boundaries

class BoundaryEvaluationTests(unittest.TestCase):
    def test_one_prediction_cannot_cover_two_reference_boundaries(self):
        result=match_boundaries([100,150],[125],30)
        self.assertEqual((result['tp'],result['fp'],result['fn']),(1,0,1))

    def test_matching_maximizes_count_before_nearest_distance(self):
        result=match_boundaries([0,10],[9,19],10)
        self.assertEqual(result['tp'],2)

    def test_exact_offsets_and_extra_boundaries(self):
        result=match_boundaries([100,200],[100,201,300],0)
        self.assertEqual((result['tp'],result['fp'],result['fn']),(1,2,1))

if __name__=='__main__':
    unittest.main()
