from pathlib import Path
import tempfile
import unittest
from scriptler.denemeler.degerlendirme.export_news_review import export
from scriptler.lib.batch_io import digest, load_json

class ReviewExportTests(unittest.TestCase):
    def test_exact_source_preserved_and_wrong_source_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); source=root/'source.txt'; raw='Açılış. Haber başladı.\n'.encode(); source.write_bytes(raw)
            review={'channel':'test','date':'date','source_sha256':digest(raw),'human_approved':False,'sections':[{'start_char':0,'kind':'other','title':'Açılış'},{'start_char':8,'kind':'news','title':'Haber'}]}
            target=root/'out'; self.assertEqual(export(source,review,target),1)
            meta=load_json(target/'haberler.json'); self.assertEqual(b''.join((target/s['file']).read_bytes() for s in meta['sections']),raw)
            with self.assertRaises(ValueError): export(source,review,target)
            source.write_text('changed',encoding='utf-8')
            with self.assertRaises(ValueError): export(source,review,root/'other')

if __name__=='__main__': unittest.main()
