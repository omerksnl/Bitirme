import json
from pathlib import Path
import tempfile
import unittest

from scriptler.denemeler.etiketleme.news_labeler import validate_labels, persist, document
from scriptler.lib.batch_io import save_json, digest


class LabelerTests(unittest.TestCase):
    def test_rejects_midword_duplicate_and_stale_revision(self):
        text='İlk haber. Yeni haber.'
        payload={'revision':0,'human_approved':False,'boundaries':[{'start_char':0,'kind':'other','title':''},{'start_char':11,'kind':'news','title':''}]}
        self.assertEqual(validate_labels(text,payload,0)['revision'],1)
        with self.assertRaises(RuntimeError): validate_labels(text,payload,1)
        payload['boundaries'][1]['start_char']=12
        with self.assertRaises(ValueError): validate_labels(text,payload,0)
        payload['boundaries'][1]['start_char']=0
        with self.assertRaises(ValueError): validate_labels(text,payload,0)

    def test_uncertain_cannot_be_human_approved(self):
        payload={'revision':0,'human_approved':True,'boundaries':[{'start_char':0,'kind':'uncertain','title':''}]}
        with self.assertRaises(ValueError): validate_labels('Bir haber',payload,0)

    def test_saved_segments_reconstruct_source_and_survive_reload(self):
        text='İlk haber. Yeni haber.\n'
        with tempfile.TemporaryDirectory() as temp:
            project=Path(temp); folder=project/'documents'/'test'; folder.mkdir(parents=True)
            save_json(project/'manifest.json',{'documents':[{'id':'test','source':'original','text_hash':digest(text.encode())}]})
            (folder/'transcript.txt').write_bytes(text.encode())
            save_json(folder/'labels.json',{'revision':0,'human_approved':False,'boundaries':[{'start_char':0,'kind':'other','title':''}]})
            payload={'revision':0,'human_approved':True,'boundaries':[{'start_char':0,'kind':'other','title':''},{'start_char':11,'kind':'news','title':'Yeni olay'}]}
            result=persist(project,'test',payload)
            self.assertEqual(document(project,'test')[2],result)
            exported=folder/'exports/revision_0001'; meta=json.loads((exported/'sections.json').read_text(encoding='utf-8'))
            self.assertEqual(b''.join((exported/s['file']).read_bytes() for s in meta['sections']),text.encode())
            with self.assertRaises(ValueError): document(project,'../../outside')
            (folder/'transcript.txt').write_text('changed',encoding='utf-8')
            with self.assertRaises(ValueError): document(project,'test')


if __name__=='__main__': unittest.main()
