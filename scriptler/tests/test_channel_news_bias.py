import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scriptler.denemeler.yerel.channel_news_bias import features, scored, select, convert_with_profile, evaluate
from scriptler.lib.batch_io import save_json


class ChannelBiasTests(unittest.TestCase):
    def test_every_word_is_a_candidate_including_cue_interior(self):
        text='Eski konu bitti Yeni haber başlıyor'
        rows=features(text,[{'start_char':0,'start_seconds':0,'end_seconds':2,'text':text}])
        self.assertIn(text.index('Yeni'),[r['position'] for r in rows])

    def test_zero_alpha_disables_channel_model_without_forcing_splits(self):
        profile={'generic':{'intercept':-2,'weights':{}},'channel_model':{'intercept':10,'weights':{}}}
        row={'position':10,'word_index':2,'features':{'prefix1=örnek':1}}
        self.assertEqual(select(scored([row],profile,0),.5),[])
        self.assertEqual(len(select(scored([row],profile,1),.5)),1)

    def test_one_peak_selected_in_nearby_word_band(self):
        rows=[{'position':20,'word_index':3,'score':.8},{'position':30,'word_index':4,'score':.9},{'position':200,'word_index':30,'score':.85}]
        self.assertEqual([r['position'] for r in select(rows,.5)],[30,200])

    def test_output_preserves_source_and_repeat_run_skips_it(self):
        raw='WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nİyi akşamlar bülten başladı\n'
        profile={'channel':'test','alpha':0,'threshold':.5,'generic':{'intercept':-5,'weights':{}},'channel_model':{'intercept':5,'weights':{}}}
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)/'output'
            self.assertEqual(convert_with_profile(raw,profile,folder,{}),'created')
            self.assertEqual((folder/'taslak_001.txt').read_bytes(),(folder/'transcript.txt').read_bytes())
            self.assertEqual(convert_with_profile(raw,profile,folder,{}),'existing')

    def test_unannotated_test_cannot_be_reported_as_zero_misses(self):
        with tempfile.TemporaryDirectory() as temp:
            job=Path(temp); save_json(job/'profile.json',{'training_dates':['A'],'development_dates':['B']})
            labels={'annotation_author':'provisional'}; docs=[{'date':'C','split':'test','annotation_complete':False}]
            with patch("scriptler.denemeler.yerel.channel_news_bias.dataset",return_value=(labels,docs)):
                with self.assertRaises(ValueError): evaluate(job)

    def test_plain_txt_works_without_invented_times(self):
        raw='İlk haber.\n\nİkinci paragraf aynı haber.\n'
        profile={'channel':'test','alpha':0,'threshold':.5,'generic':{'intercept':-5,'weights':{}},'channel_model':{'intercept':5,'weights':{}}}
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)/'output'; convert_with_profile(raw,profile,folder,{})
            self.assertEqual((folder/'transcript.txt').read_bytes(),raw.encode())

    def test_overlapping_training_and_test_day_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            job=Path(temp); save_json(job/'profile.json',{'training_dates':['A'],'development_dates':['B']})
            docs=[{'date':'A','split':'test','annotation_complete':True}]
            with patch("scriptler.denemeler.yerel.channel_news_bias.dataset",return_value=({},docs)):
                with self.assertRaises(ValueError): evaluate(job)


if __name__=='__main__': unittest.main()
