"""Integration checks for the local portfolio demo; no external sends."""
import os
from pathlib import Path
import tempfile
import unittest

_tmp = tempfile.TemporaryDirectory()
os.environ['DATABASE_URL'] = 'sqlite:///' + str(Path(_tmp.name) / 'test.db').replace('\\', '/')
os.environ['WA_PROVIDER'] = 'cloud'

from fastapi.testclient import TestClient
from app.main import app
from app.models import engine


def tearDownModule():
    engine.dispose()
    _tmp.cleanup()


class DemoSmokeTest(unittest.TestCase):
    def test_demo_read_flow(self):
        with TestClient(app) as client:
            self.assertEqual(client.get('/').status_code, 200)
            self.assertEqual(client.get('/api/auth/me').status_code, 401)
            bad = client.post('/api/auth/login', data={'username': 'admin', 'password': 'wrong'})
            self.assertEqual(bad.status_code, 401)
            login = client.post('/api/auth/login', data={'username': 'admin', 'password': 'admin123'})
            self.assertEqual(login.status_code, 200)
            headers = {'Authorization': 'Bearer ' + login.json()['access_token']}
            for route in ['/api/auth/me', '/api/analytics/resumen', '/api/analytics/cartera', '/api/orchestrator/plan']:
                response = client.get(route, headers=headers)
                self.assertEqual(response.status_code, 200, route)
                self.assertTrue(response.json(), route)


if __name__ == '__main__':
    unittest.main()
