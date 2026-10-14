import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from scriptler.lib.batch_io import load_json, save_json

class JsonPersistenceTests(unittest.TestCase):
    def test_replace_denied_keeps_new_value_journal_and_old_backup(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'state.json'; path.write_text('{"stage":"old"}',encoding='utf-8')
            with patch.object(Path,'replace',side_effect=PermissionError('Denied')):
                save_json(path,{'stage':'new','batch_id':'test-id'})
            self.assertEqual(load_json(path)['stage'],'new')
            self.assertEqual(load_json(path.with_suffix('.json.bak'))['stage'],'old')
            self.assertEqual(load_json(path.with_suffix('.json.tmp'))['batch_id'],'test-id')

    def test_interrupted_in_place_write_recovers_complete_journal(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'state.json'; path.write_text('{',encoding='utf-8')
            path.with_suffix('.json.tmp').write_text('{"creation_pending":true}',encoding='utf-8')
            self.assertTrue(load_json(path)['creation_pending'])

if __name__=='__main__': unittest.main()
