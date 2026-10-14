import unittest
from audit_news_cost_results import diagnose, source_matches


class CostOutputAuditTests(unittest.TestCase):
    def data(self):
        return {'text': 'Eski olay bitti. Yeni olay başladı.', 'units': [
            {'id': '0', 'start_char': 0, 'text': 'Eski olay bitti.'},
            {'id': '1', 'start_char': 17, 'text': 'Yeni olay başladı.'}]}

    def opening(self):
        return {'unit': '0', 'start_quote': 'Eski olay', 'kind': 'news'}

    def test_nearby_wrong_id_is_only_diagnostic_never_production_accepted(self):
        result = diagnose(self.data(), {'segments': [self.opening(), {'unit': '0', 'start_quote': 'Yeni olay başladı.', 'kind': 'news'}]})
        self.assertTrue(result['diagnostic_sequence_complete'])
        self.assertFalse(result['production_accepted'])
        self.assertEqual(result['segments'][1]['start_char'], 17)

    def test_punctuation_tolerance_does_not_change_source_words(self):
        d = self.data()
        result = diagnose(d, {'segments': [{'unit': '0', 'start_quote': 'Eski olay bitti', 'kind': 'news'}]})
        self.assertEqual(result['findings'][0]['matching_method'], 'trailing_punctuation_ignored_only')
        self.assertEqual(d['text'], 'Eski olay bitti. Yeni olay başladı.')
        self.assertFalse(result['production_accepted'])
        altered = diagnose(d, {'segments': [{'unit': '0', 'start_quote': 'Eski haber bitti.', 'kind': 'news'}]})
        self.assertEqual(altered['unresolved_indices'], [0])

    def test_ambiguous_duplicate_remains_unresolved(self):
        d = {'text': 'Eski olay. Aynı haber. Aynı haber.', 'units': [
            {'id': '0', 'start_char': 0, 'text': 'Eski olay.'},
            {'id': '1', 'start_char': 11, 'text': 'Aynı haber.'},
            {'id': '2', 'start_char': 23, 'text': 'Aynı haber.'}]}
        result = diagnose(d, {'segments': [self.opening(), {'unit': '0', 'start_quote': 'Aynı haber.', 'kind': 'news'}]})
        self.assertEqual(result['unresolved_indices'], [1])
        self.assertFalse(result['diagnostic_sequence_complete'])
        self.assertEqual(source_matches(d['text'], ''), [])


if __name__ == '__main__': unittest.main()
