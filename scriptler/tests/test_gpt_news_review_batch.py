import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from gpt_news_review_batch import ROOT, MODEL, make_request, split_payload, collect_records, reserve_budget, schema, usage_cost_usd, cost_bound, compact_timeline
from openai_news_batch import save_json, digest, load_json


class GptNewsReviewTests(unittest.TestCase):
    def data(self):
        return {'text': 'Eski olay devam. Yeni olay başladı.\n', 'units': [
            {'id': 'U00000', 'start_char': 0, 'text': 'Eski olay devam. Yeni olay başladı.'}]}

    def payload(self):
        return {'segments': [{'unit': 'U00000', 'start_quote': 'Eski olay', 'kind': 'news'},
                             {'unit': 'U00000', 'start_quote': 'Yeni olay başladı.', 'kind': 'news'}]}

    def test_model_may_add_missing_cue_interior_boundary_without_counting_words(self):
        data = self.data()
        request = make_request('doc', data, {'sections': [{'start_char': 0}]}, 4096)
        self.assertEqual(request['body']['model'], MODEL)
        self.assertEqual(request['body']['reasoning']['effort'], 'low')
        segments = split_payload(data, self.payload())
        self.assertEqual(segments[1]['start_char'], data['text'].index('Yeni'))

    def test_request_preserves_selected_channel(self):
        request = make_request('ATV_doc', self.data(), {'sections': [{'start_char': 0}]}, 4096, channel='ATV')
        self.assertTrue(request['body']['input'][1]['content'].startswith('Kanal: ATV\n'))

    def test_compact_request_preserves_source_and_boundary_coordinates(self):
        original = self.data()
        compact = compact_timeline(original)
        self.assertEqual(original['units'][0]['id'], 'U00000')
        self.assertEqual(compact['text'], original['text'])
        self.assertEqual(compact['units'][0]['start_char'], original['units'][0]['start_char'])
        request = make_request('doc', compact, {'sections': [{'start_char': 0}]}, 4096)
        unit = request['body']['text']['format']['schema']['properties']['segments']['items']['properties']['unit']
        self.assertEqual(unit, {'type': 'string', 'pattern': '^[0-9]+$'})
        self.assertIn('unit="17"', request['body']['input'][0]['content'])
        payload = {'segments': [{**s, 'unit': '0'} for s in self.payload()['segments']]}
        self.assertEqual([s['start_char'] for s in split_payload(compact, payload)],
                         [s['start_char'] for s in split_payload(original, self.payload())])

    def test_long_bulletin_does_not_exceed_api_enum_limit(self):
        definition = schema([{'id': f'U{i:05d}'} for i in range(1041)])
        unit = definition['properties']['segments']['items']['properties']['unit']
        self.assertNotIn('enum', unit)
        self.assertEqual(unit['pattern'], '^U[0-9]{5}$')

    def test_source_correction_repetition_missing_opening_and_disorder_rejected(self):
        p = self.payload()
        p['segments'][1]['start_quote'] = 'Yeni haber başladı.'
        with self.assertRaises(ValueError): split_payload(self.data(), p)
        repeated = {'text': 'Aynı söz Aynı söz', 'units': [{'id': 'U00000', 'start_char': 0, 'text': 'Aynı söz Aynı söz'}]}
        with self.assertRaises(ValueError): split_payload(repeated, {'segments': [{'unit': 'U00000', 'start_quote': 'Aynı söz', 'kind': 'news'}]})
        with self.assertRaises(ValueError): split_payload(self.data(), {'segments': self.payload()['segments'][1:]})
        with self.assertRaises(ValueError): split_payload(self.data(), {'segments': list(reversed(self.payload()['segments']))})

    def manifest(self, job):
        data = self.data()
        raw = data['text'].encode()
        (job / 'transcript.txt').write_bytes(raw)
        save_json(job / 'timeline.json', data)
        return {'requests': [{'custom_id': 'doc', 'date': 'test', 'snapshot': 'transcript.txt',
                             'timeline': 'timeline.json', 'sha256': digest(raw)}]}

    def record(self, payload=None, status='completed'):
        return {'custom_id': 'doc', 'response': {'status_code': 200, 'body': {
            'status': status, 'output': [{'content': [{'type': 'output_text', 'text': json.dumps(payload or self.payload())}]}],
            'usage': {'input_tokens': 100, 'output_tokens': 80, 'output_tokens_details': {'reasoning_tokens': 60}}}}}

    def test_collection_is_idempotent_preserves_bytes_and_does_not_double_bill_reasoning(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'work') as temp:
            job = Path(temp)
            manifest = self.manifest(job)
            output = job / 'output.jsonl'
            output.write_text(json.dumps(self.record()), encoding='utf8')
            with patch('gpt_news_review_batch.checked_manifest', return_value=manifest):
                first = collect_records(job, output)
                second = collect_records(job, output)
            self.assertEqual(first['exported'], 1)
            self.assertEqual(second['exported'], 1)
            self.assertAlmostEqual(first['usage_cost_usd_conservative'], .0005)
            folder = job / 'haberler/KanalD/test'
            saved = load_json(folder / 'sections.json')
            self.assertEqual(b''.join((folder / s['file']).read_bytes() for s in saved['sections']), self.data()['text'].encode())
            self.assertFalse(saved['human_approved'])

    def test_duplicate_or_truncated_model_response_does_not_export(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'work') as temp:
            job = Path(temp)
            manifest = self.manifest(job)
            output = job / 'output.jsonl'
            output.write_text('\n'.join([json.dumps(self.record())] * 2), encoding='utf8')
            with patch('gpt_news_review_batch.checked_manifest', return_value=manifest):
                report = collect_records(job, output)
                self.assertEqual(report['exported'], 0)
                output.write_text(json.dumps(self.record(status='incomplete')), encoding='utf8')
                report = collect_records(job, output)
                self.assertEqual(report['exported'], 0)
                self.assertEqual(report['failed'], 1)

    def test_same_date_different_channels_export_to_separate_paths(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'work') as temp:
            job = Path(temp)
            manifest = self.manifest(job)
            first = {**manifest['requests'][0], 'custom_id': 'KanalD_day', 'channel': 'KanalD'}
            second = {**first, 'custom_id': 'ATV_day', 'channel': 'ATV'}
            manifest['requests'] = [first, second]
            output = job / 'output.jsonl'
            output.write_text('\n'.join(json.dumps({**self.record(), 'custom_id': d['custom_id']}) for d in [first, second]), encoding='utf8')
            with patch('gpt_news_review_batch.checked_manifest', return_value=manifest):
                report = collect_records(job, output)
            self.assertEqual(report['exported'], 2)
            self.assertTrue((job / 'haberler/KanalD/test/sections.json').exists())
            self.assertTrue((job / 'haberler/ATV/test/sections.json').exists())

    def test_luna_collection_uses_its_own_rates(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'work') as temp:
            job = Path(temp)
            manifest = self.manifest(job)
            manifest['model'] = 'gpt-6-luna'
            output = job / 'output.jsonl'
            output.write_text(json.dumps(self.record()), encoding='utf8')
            with patch('gpt_news_review_batch.checked_manifest', return_value=manifest):
                report = collect_records(job, output)
            self.assertEqual(report['model'], 'gpt-6-luna')
            self.assertAlmostEqual(report['usage_cost_usd_conservative'], .000025)

    def test_cache_writes_and_reads_use_distinct_rates_without_double_counting(self):
        usage = {'input_tokens': 1000, 'input_tokens_details': {'cached_tokens': 400, 'cache_write_tokens': 500},
                 'output_tokens': 200, 'output_tokens_details': {'reasoning_tokens': 150}}
        self.assertAlmostEqual(usage_cost_usd(usage, 'gpt-6-luna'), (100 * .05 + 400 * .005 + 500 * .0625 + 200 * .25) / 1e6)
        self.assertAlmostEqual(usage_cost_usd(usage, MODEL), (100 * 1 + 400 * .05 + 500 * 1.25 + 200 * 5) / 1e6)
        usage['input_tokens_details']['cache_write_tokens'] = 700
        with self.assertRaises(ValueError): usage_cost_usd(usage, MODEL)

    def test_new_budget_bound_covers_all_input_being_cache_written(self):
        encoding = type('Encoding', (), {'encode': lambda self, value: [0] * 1000})()
        request = make_request('doc', self.data(), {'sections': [{'start_char': 0}]}, 4096)
        bound = cost_bound(request, encoding)
        self.assertEqual(bound['input_cost_multiplier_bound'], 1.25)
        self.assertAlmostEqual(bound['estimated_max_usd'], (bound['input_tokens_with_margin'] * 1.25 + 4096 * 5) / 1e6)

    def test_budget_reserved_once_and_refuses_pipeline_overspend(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'work') as temp:
            job = Path(temp)
            ledger = job / 'ledger.json'
            manifest = {'requests_sha256': 'frozen', 'budget': {'estimated_max_usd': .12}}
            with patch('gpt_news_review_batch.LEDGER', ledger):
                reserve_budget(job, manifest)
                reserve_budget(job, manifest)
                self.assertEqual(len(load_json(ledger)['jobs']), 1)
                save_json(ledger, {'limit_usd': 10., 'jobs': {'older': {'reserved_usd': 9.99}}})
                with self.assertRaises(ValueError): reserve_budget(job, manifest)


if __name__ == '__main__':
    unittest.main()
