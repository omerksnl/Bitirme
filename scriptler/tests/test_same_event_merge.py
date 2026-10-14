import tempfile
from pathlib import Path
import unittest
from scriptler.denemeler.yerel.same_event_merge import pairs, decisions, export_merged
from scriptler.lib.batch_io import load_json


class SameEventMergeTests(unittest.TestCase):
    def test_context_can_cross_short_original_sections(self):
        text='Eski olay devam ediyor yeni ayrıntı sonra başka olay başlıyor'
        a=text.index('yeni'); b=text.index('başka'); rows=pairs(text,[a,b],{a:.8,b:.9})
        self.assertIn('başka olay',rows[0]['texts'][1])
        self.assertNotIn('başka olay',rows[0]['texts'][3])
        self.assertEqual(rows[0]['features']['boundary_score'],.8)

    def test_source_position_is_never_produced_or_shifted_by_model(self):
        rows=[{'position':10,'features':{'context_similarity':.95}},{'position':30,'features':{'context_similarity':.1}}]
        result=decisions(rows,{'intercept':1,'weights':{'context_similarity':-3}},.5)
        self.assertEqual([r['position'] for r in result],[10,30])
        self.assertEqual([r['decision'] for r in result],['merge','keep'])

    def test_merge_preserves_whitespace_and_only_removes_existing_cuts(self):
        text='İlk haber.\nAyrıntı. Yeni olay.\n'; cuts=[text.index('Ayrıntı'),text.index('Yeni')]
        ds=[{'position':cuts[0],'decision':'merge'},{'position':cuts[1],'decision':'keep'}]
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'merged'; kept=export_merged(text,cuts,ds,out)
            self.assertEqual(kept,[cuts[1]])
            meta=load_json(out/'sections.json')
            self.assertEqual(b''.join((out/s['file']).read_bytes() for s in meta['sections']),text.encode())
            self.assertFalse(meta['human_approved'])
            with self.assertRaises(ValueError): export_merged(text,cuts,ds,out)

    def test_rejects_missing_decision_and_nonword_cut(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError): export_merged('Bir haber',[4],[],Path(temp)/'a')
            with self.assertRaises(ValueError): export_merged('Bir haber',[5],[{'position':5,'decision':'keep'}],Path(temp)/'b')
        with self.assertRaises(ValueError): pairs('Bir haber',[0],{})
        with self.assertRaises(ValueError): pairs('Bir haber',[4,4],{})


if __name__=='__main__': unittest.main()
