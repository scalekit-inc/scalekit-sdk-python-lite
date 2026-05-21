"""
Live integration tests for organization slug and logo_url features.

Reads credentials from .env in the repo root:

    SCALEKIT_ENVIRONMENT_URL=https://...
    SCALEKIT_CLIENT_ID=skc_...
    SCALEKIT_CLIENT_SECRET=...

Run:
    python -m pytest tests/test_organization_slug_logo.py -v
"""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# ---------------------------------------------------------------------------
# Load .env from repo root
# ---------------------------------------------------------------------------

def _load_env(path):
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                key, _, value = line.partition('=')
                key = key.strip()
                value = value.strip().strip("'\"")
                if key and key not in os.environ:
                    os.environ[key] = value
    except IOError:
        pass

_load_env(os.path.join(os.path.dirname(__file__), '..', '.env'))

ENVIRONMENT_URL = os.environ['SCALEKIT_ENVIRONMENT_URL']
CLIENT_ID = os.environ['SCALEKIT_CLIENT_ID']
CLIENT_SECRET = os.environ['SCALEKIT_CLIENT_SECRET']


class TestOrganizationSlugAndLogo(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from scalekit import ScalekitClient
        cls.client = ScalekitClient(ENVIRONMENT_URL, CLIENT_ID, CLIENT_SECRET)
        cls._unique = str(int(time.time()))

    def setUp(self):
        self.org_id = None

    def tearDown(self):
        if self.org_id:
            try:
                self.client.organization.delete(self.org_id)
            except Exception:
                pass

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _create_plain_org(self):
        """Create a plain org without slug/logo and return its id."""
        resp = self.client.organization.create(
            'Slug Logo Test Org {}'.format(self._unique)
        )
        return resp['organization']['id']

    # -----------------------------------------------------------------------
    # Tests
    # -----------------------------------------------------------------------

    def test_create_with_logo_url(self):
        logo = 'https://logo.debounce.com/microsoft.com'
        result = self.client.organization.create(
            'Acme Corporation',
            logo_url=logo,
        )
        self.assertIn('organization', result)
        org = result['organization']
        self.org_id = org['id']
        self.assertEqual(org['logo_url'], logo)

    def test_create_with_slug(self):
        slug = 'app.acmecorp.com'
        result = self.client.organization.create(
            'Acme Corporation',
            slug=slug,
        )
        self.assertIn('organization', result)
        org = result['organization']
        self.org_id = org['id']
        self.assertTrue(org.get('slug'), 'expected slug to be set on created org')

    def test_update_logo_url(self):
        self.org_id = self._create_plain_org()
        logo = 'https://logo.debounce.com/microsoft.com'
        result = self.client.organization.update(
            self.org_id,
            logo_url=logo,
        )
        self.assertIn('organization', result)
        org = result['organization']
        self.assertEqual(org['logo_url'], logo)

    def test_update_slug_and_metadata(self):
        self.org_id = self._create_plain_org()
        slug = 'app.acmecorp.com'
        metadata = {'custom_domain': 'app.acmecorp.com'}
        result = self.client.organization.update(
            self.org_id,
            slug=slug,
            metadata=metadata,
        )
        self.assertIn('organization', result)
        org = result['organization']
        self.assertTrue(org.get('slug'), 'expected slug to be set after update')
        self.assertEqual(org.get('metadata', {}).get('custom_domain'), 'app.acmecorp.com')


if __name__ == '__main__':
    unittest.main()
