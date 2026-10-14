import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scriptler.denemeler.api.daily_news_pipeline import timeline, windows, validate, process_lock, database, ingest, request_for, consume, prepare, verified_timeline
from scriptler.lib.batch_io import save_json

VTT='''WEBVTT

00:00:00.000 --> 00:00:02.000
Eski haber başladı şimdi

00:00:01.000 --> 00:00:03.000
başladı şimdi devam ediyor

00:00:05.000 --> 00:00:06.000
Yeni olay başladı
'''


class DailyPipelineTests(unittest.TestCase):
    def test_rolling_overlap_preserves_time_and_source_offsets(self):
        data=timeline(VTT,{})
        self.assertEqual(data['text'],'Eski haber başladı şimdi devam ediyor Yeni olay başladı\n')
        self.assertEqual(data['units'][1]['text'],'devam ediyor')
        self.assertEqual(data['units'][1]['start_seconds'],1)
        for unit in data['units']:
            self.assertTrue(data['text'][unit['start_char']:].startswith(unit['text']))

    def test_pause_keeps_repeated_statement(self):
        vtt=VTT.replace('Yeni olay başladı','Eski haber başladı şimdi')
        self.assertEqual(timeline(vtt,{})['text'].count('Eski haber başladı şimdi'),2)

    def test_windows_cover_every_unit_once_with_context(self):
        units=[{'text':'kelime '*60} for _ in range(7)]
        parts=list(windows(units,100,60))
        self.assertEqual([i for begin,end,_,_ in parts for i in range(begin,end)],list(range(7)))
        self.assertTrue(parts[1][2]<parts[1][0])

    def test_boundary_word_offset_and_core_validation(self):
        units=timeline(VTT,{})['units']; ref={'core_begin':0,'core_end':3}
        first={'unit_id':'U00000','start_word':0,'kind':'other','event':'Açılış','uncertain':False}
        second={'unit_id':'U00002','start_word':1,'kind':'news','event':'Yeni olay','uncertain':False}
        result=validate({'boundaries':[first,second]},ref,units)
        self.assertEqual(result[1]['start_char'],units[2]['start_char']+5)
        with self.assertRaises(ValueError): validate({'boundaries':[second]},ref,units)
        with self.assertRaises(ValueError): validate({'boundaries':[first,{**second,'start_word':100}]},ref,units)

    def make_document(self,root):
        source=root/'input'; source.mkdir(); (source/'sample.vtt').write_text(VTT,encoding='utf-8')
        args=SimpleNamespace(root=root/'output',input=source,limit=0,core_words=100,context_words=50,
                             model='gpt-4.1-mini-2025-04-14',budget_usd=.2,input_price=.2,output_price=.8)
        args.root.mkdir(); db=database(args.root); ingest(db,args)
        return args,db,db.execute('SELECT * FROM documents').fetchone()

    def test_ingest_is_idempotent_and_changed_source_creates_version(self):
        with tempfile.TemporaryDirectory() as temporary:
            args,db,doc=self.make_document(Path(temporary))
            ingest(db,args); self.assertEqual(db.execute('SELECT count(*) FROM documents').fetchone()[0],1)
            (args.input/'sample.vtt').write_text(VTT.replace('Yeni olay','Farklı olay'),encoding='utf-8')
            ingest(db,args); self.assertEqual(db.execute('SELECT count(*) FROM documents').fetchone()[0],2)
            (Path(doc['folder'])/'transcript.txt').write_text('changed',encoding='utf-8')
            with self.assertRaises(ValueError): verified_timeline(doc)
            db.close()

    def test_missing_api_result_blocks_export_then_cache_reuses_valid_result(self):
        with tempfile.TemporaryDirectory() as temporary:
            args,db,doc=self.make_document(Path(temporary)); units=verified_timeline(doc)['units']
            job=args.root/'batches'/'test'; job.mkdir(parents=True)
            ref={'custom_id':'request1','doc_id':doc['id'],'core_begin':0,'core_end':3}
            save_json(job/'manifest.json',{'requests':[ref],'documents':[{'doc_id':doc['id'],'all_requests':[ref]}]})
            consume(db,job,[])
            self.assertEqual(db.execute('SELECT status FROM documents').fetchone()[0],'retry')
            self.assertFalse((Path(doc['folder'])/'news_drafts'/'sections.json').exists())
            payload={'boundaries':[{'unit_id':'U00000','start_word':0,'kind':'news','event':'Olay','uncertain':False}]}
            record={'custom_id':'request1','response':{'status_code':200,'body':{'status':'completed','output':[{'content':[{'type':'output_text','text':json.dumps(payload)}]}]}}}
            consume(db,job,[record]); self.assertEqual(db.execute('SELECT status FROM documents').fetchone()[0],'draft_ready')
            self.assertEqual((Path(doc['folder'])/'news_drafts'/'001_news.txt').read_bytes(),verified_timeline(doc)['text'].encode())
            self.assertEqual(db.execute('SELECT count(*) FROM responses').fetchone()[0],1)
            db.close()

    def test_budget_exhaustion_prevents_batch_creation(self):
        with tempfile.TemporaryDirectory() as temporary:
            args,db,_=self.make_document(Path(temporary)); args.budget_usd=0
            self.assertIsNone(prepare(db,args)); self.assertFalse((args.root/'batches').exists()); db.close()

    def test_process_lock_prevents_two_workers(self):
        with tempfile.TemporaryDirectory() as temporary:
            with process_lock(Path(temporary)):
                with self.assertRaises(ValueError):
                    with process_lock(Path(temporary)): pass

    def test_retry_batch_only_contains_missing_window(self):
        with tempfile.TemporaryDirectory() as temporary:
            args,db,doc=self.make_document(Path(temporary))
            raw='WEBVTT\n\n'+ '\n\n'.join(f'00:00:{i*5:02d}.000 --> 00:00:{i*5+2:02d}.000\n'+(f'konu{i} '*60) for i in range(3))
            (args.input/'sample.vtt').write_text(raw,encoding='utf-8')
            # Ignore the small fixture; test a two-window source.
            db.execute("UPDATE documents SET status='draft_ready'"); db.commit(); ingest(db,args)
            job=prepare(db,args); manifest=json.loads((job/'manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(manifest['request_count'],2)
            first=manifest['requests'][0]
            payload={'boundaries':[{'unit_id':'U00000','start_word':0,'kind':'news','event':'Olay','uncertain':False}]}
            record={'custom_id':first['custom_id'],'response':{'status_code':200,'body':{'status':'completed','output':[{'content':[{'type':'output_text','text':json.dumps(payload)}]}]}}}
            consume(db,job,[record])
            retry=prepare(db,args); manifest2=json.loads((retry/'manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(manifest2['request_count'],1)
            self.assertNotEqual(manifest2['requests'][0]['custom_id'],first['custom_id'])
            db.close()

    def test_identical_file_under_another_name_is_not_reprocessed(self):
        with tempfile.TemporaryDirectory() as temporary:
            args,db,_=self.make_document(Path(temporary))
            (args.input/'duplicate.vtt').write_bytes((args.input/'sample.vtt').read_bytes())
            ingest(db,args)
            self.assertEqual(db.execute('SELECT count(*) FROM documents').fetchone()[0],1)
            db.close()


if __name__=='__main__':
    unittest.main()
