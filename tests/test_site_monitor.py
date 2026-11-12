import importlib.util
import unittest
import urllib.error
import urllib.request
from pathlib import Path

spec = importlib.util.spec_from_file_location('monitor', Path(__file__).parents[1] / 'scripts/site_monitor.py')
monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monitor)

BASE = 'https://example.com'
HEADERS = {'Content-Security-Policy': "default-src 'self'; frame-ancestors 'self'", 'Strict-Transport-Security': 'max-age=31536000',
           'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'strict-origin-when-cross-origin', 'Permissions-Policy': 'camera=()'}


def response(body, status=200, headers=None):
    return {'body': body, 'status': status, 'headers': HEADERS if headers is None else headers, 'error': None}


class MonitorTests(unittest.TestCase):
    def run_monitor(self, page=None, sitemap=None, contact=None):
        fixtures = {
            '/': page or response('<html><title>Koralya</title><main><a href="/contact/">Contact</a><a href="https://elsewhere.test/">Externe</a></main></html>'),
            '/contact/': response('<html><title>Contact</title><main>Contact</main></html>'),
            '/robots.txt': response('User-agent: *\nSitemap: https://example.com/sitemap.xml'),
            '/sitemap.xml': sitemap or response('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://example.com/</loc></url></urlset>'),
            '/api/contact/config': contact or response('', 404),
        }
        seen = []

        def fetch(url, timeout):
            self.assertEqual(monitor.origin(url), monitor.origin(BASE))
            path = urllib.parse.urlsplit(url).path
            seen.append(path)
            return fixtures.get(path, response('', 404))

        report = monitor.run({'base_url': BASE, 'pages': ['/', '/contact/']}, fetch)
        self.assertEqual(len(seen), len(set(seen)))
        return report

    def test_manual_contact_is_not_an_outage(self):
        report = self.run_monitor()
        self.assertEqual(report['state'], 'ok')
        self.assertTrue(any(f['path'] == '/api/contact/config' and f['severity'] == 'info' for f in report['findings']))

    def test_missing_headers_are_warnings(self):
        report = self.run_monitor(page=response('<html><title>Home</title><main>OK</main></html>', headers={}))
        self.assertEqual(report['state'], 'warning')

    def test_broken_internal_link_is_error(self):
        report = self.run_monitor(page=response('<html><title>Home</title><main><a href="/missing/">Lien</a></main></html>'))
        self.assertEqual(report['state'], 'error')
        self.assertTrue(any(f['path'] == '/missing/' for f in report['findings']))

    def test_soft_404_is_rejected(self):
        report = self.run_monitor(page=response('Not found'))
        self.assertEqual(report['state'], 'error')

    def test_html_returned_as_sitemap_is_error(self):
        self.assertEqual(self.run_monitor(sitemap=response('<html>Fallback</html>'))['state'], 'error')

    def test_external_sitemap_is_error(self):
        body = '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://elsewhere.test/</loc></url></urlset>'
        self.assertEqual(self.run_monitor(sitemap=response(body))['state'], 'error')

    def test_network_error_is_error(self):
        self.assertEqual(self.run_monitor(page={'body': '', 'status': None, 'headers': {}, 'error': 'Connexion impossible'})['state'], 'error')

    def test_rejects_external_and_insecure_links(self):
        for href in ['http://example.com/', 'https://elsewhere.test/', '//elsewhere.test/', 'mailto:info@example.com', 'https://user:pass@example.com/']:
            self.assertIsNone(monitor.internal_url(BASE, href))
        self.assertEqual(monitor.internal_url(BASE, '/contact/#form'), BASE + '/contact/')

    def test_redirects_cannot_leave_site(self):
        handler = monitor.SameOriginRedirect(BASE)
        with self.assertRaises(urllib.error.URLError):
            handler.redirect_request(urllib.request.Request(BASE), None, 302, '', {}, 'https://elsewhere.test/')


if __name__ == '__main__':
    unittest.main()
