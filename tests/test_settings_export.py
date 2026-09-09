import functools
import http.server
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import digest


class SettingsExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name, value in {
            'OUTPUT_DIR': self.root, 'CONFIG_FILE': self.root / 'config.json',
            'STATE_FILE': self.root / '.state.json', 'DIGEST_LOCK_FILE': self.root / '.digest.lock',
        }.items():
            patcher = patch.object(digest, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.source = self.root / 'claude'
        folder = self.source / 'projects' / '-old-encoded-name'
        folder.mkdir(parents=True)
        (folder / 'example.jsonl').write_text(json.dumps({
            'type': 'user', 'cwd': '/work/my-project', 'timestamp': '2026-09-09T12:00:00Z',
            'message': {'content': 'Please repeat this workflow'}
        }) + '\n')
        self.config = {'claude_dir': str(self.source), 'codex_dir': None, 'projects': []}
        digest.write_json_atomic(digest.CONFIG_FILE, self.config)

    def test_directory_moves_and_config_edits_apply_to_cached_sessions(self):
        first = digest.run_digest(quiet=True)[0]
        self.assertEqual(first['project_key'], '/work/my-project')
        self.config['projects'] = [{'id': 'p', 'name': 'Backend', 'category': 'CoinKarma',
                                    'paths': ['/work/my-project', '/new/backend']}]
        digest.write_json_atomic(digest.CONFIG_FILE, self.config)
        self.assertEqual(digest.run_digest(quiet=True)[0]['project'], 'Backend')
        self.config['projects'][0]['name'] = 'Renamed'
        digest.write_json_atomic(digest.CONFIG_FILE, self.config)
        self.assertEqual(digest.run_digest(quiet=True)[0]['project'], 'Renamed')
        self.config['projects'] = []
        digest.write_json_atomic(digest.CONFIG_FILE, self.config)
        self.assertEqual(digest.run_digest(quiet=True)[0]['project'], '/work/my-project')
        self.assertTrue((self.source / 'projects' / '-old-encoded-name' / 'example.jsonl').exists())

    def test_longest_path_wins_and_sibling_does_not_match(self):
        config = {'projects': [
            {'id': 'a', 'name': 'Parent', 'category': 'C', 'paths': ['/work']},
            {'id': 'b', 'name': 'Child', 'category': 'C', 'paths': ['/work/repo']}]}
        self.assertEqual(digest.assign_project({'project': '/work/repo/sub'}, config)['project'], 'Child')
        self.assertEqual(digest.assign_project({'project': '/work/repository'}, config)['project'], 'Parent')

    def test_export_only_selected_and_reject_disabled_or_unknown(self):
        digest.run_digest(quiet=True)
        result = digest.export_sessions(['example'])
        output = Path(result['path'])
        self.assertEqual([p.name for p in (output / 'sessions').iterdir()], ['example.md'])
        self.assertIn('訊息 1', (output / 'sessions' / 'example.md').read_text())
        with self.assertRaises(ValueError):
            digest.export_sessions(['../../config'])
        self.config['claude_dir'] = None
        digest.write_json_atomic(digest.CONFIG_FILE, self.config)
        with self.assertRaises(ValueError):
            digest.export_sessions(['example'])

    def test_missing_source_does_not_replace_index(self):
        digest.run_digest(quiet=True)
        original = (self.root / 'index.json').read_bytes()
        self.config['claude_dir'] = str(self.root / 'missing')
        digest.write_json_atomic(digest.CONFIG_FILE, self.config)
        with self.assertRaises(ValueError):
            digest.run_digest(quiet=True)
        self.assertEqual((self.root / 'index.json').read_bytes(), original)

    def test_discovery_does_not_write_conversations(self):
        data = digest.discover_projects(self.config)
        self.assertEqual(data, {'paths': ['/work/my-project'], 'errors': []})
        self.assertFalse((self.root / 'sessions').exists())

    def test_http_settings_digest_export_and_private_files(self):
        handler = functools.partial(digest.DigestHandler, directory=str(self.root))
        server = http.server.HTTPServer(('127.0.0.1', 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        base = f'http://127.0.0.1:{server.server_port}'
        def post(path, body):
            return json.load(urlopen(Request(base+path, json.dumps(body).encode(), {'Content-Type':'application/json'})))
        # Browser reload must not reuse a stale UI through a 304 response.
        for page in ('/', '/prototype.html?v=test'):
            with urlopen(base + page) as response:
                modified = response.headers['Last-Modified']
                self.assertEqual(response.headers['Cache-Control'], 'no-store')
            request = Request(base + page, headers={'If-Modified-Since': modified})
            with urlopen(request) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.read(), (digest.APP_DIR / 'prototype.html').read_bytes())
        self.assertTrue(post('/api/config', self.config)['ok'])
        self.assertEqual(post('/api/digest', {})['count'], 1)
        self.assertEqual(post('/api/export', {'ids':['example']})['count'], 1)
        with self.assertRaises(HTTPError):
            urlopen(base + '/config.json')
        invalid = dict(self.config, projects=[{'id':'a','name':'','category':'C','paths':['/work']}])
        with self.assertRaises(HTTPError):
            post('/api/config', invalid)
        self.assertEqual(json.loads(digest.CONFIG_FILE.read_text()), self.config)
