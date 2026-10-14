import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from gpt_news_review_batch import BUNDLE, pilot_sources, compact_timeline, make_request
from openai_news_batch import ROOT, load_json, digest


class PilotBundleTests(unittest.TestCase):
    def test_tracked_sources_rebuild_the_exact_selected_sol_requests(self):
        docs = load_json(BUNDLE / 'pilot_sources.json')['documents']
        sources = pilot_sources()
        self.assertEqual(len(sources), 3)
        for doc, source in zip(docs, sources):
            request = make_request(doc['channel'] + '_' + doc['date'], compact_timeline(source['data']),
                                   source['draft'], 4096, doc['channel'])
            raw = json.dumps(request, ensure_ascii=False, separators=(',', ':')).encode()
            self.assertEqual(digest(raw), doc['approved_request_sha256'])
            self.assertEqual(digest(source['data']['text'].encode()), doc['text_sha256'])

    def test_windows_checkout_line_endings_preserve_frozen_requests(self):
        docs = load_json(BUNDLE / 'pilot_sources.json')['documents']
        with tempfile.TemporaryDirectory(dir=ROOT / 'work') as temp:
            mirror = Path(temp)
            bundle = mirror / 'data/haber_pipeline'
            shutil.copytree(BUNDLE, bundle)
            corrections = mirror / 'scriptler/vtt_word_corrections.json'
            corrections.parent.mkdir()
            corrections.write_bytes((ROOT / 'scriptler/vtt_word_corrections.json').read_bytes())
            for doc in docs:
                target = mirror / doc['source']
                target.parent.mkdir(parents=True, exist_ok=True)
                raw = (ROOT / doc['source']).read_bytes().replace(b'\r\n', b'\n')
                target.write_bytes(raw.replace(b'\n', b'\r\n'))
            with patch('gpt_news_review_batch.ROOT', mirror), patch('gpt_news_review_batch.BUNDLE', bundle):
                sources = pilot_sources()
            for doc, source in zip(docs, sources):
                request = make_request(doc['channel'] + '_' + doc['date'], compact_timeline(source['data']),
                                       source['draft'], 4096, doc['channel'])
                raw = json.dumps(request, ensure_ascii=False, separators=(',', ':')).encode()
                self.assertEqual(digest(raw), doc['approved_request_sha256'])


if __name__ == '__main__':
    unittest.main()
