import unittest
from datetime import datetime, timezone
from scripts import source_watch as watch

NOW = datetime(2026, 11, 13, 12, tzinfo=timezone.utc)
SOURCE = {'id': 'official', 'name': 'Source officielle', 'category': 'Web',
          'feed_url': 'https://example.com/feed.xml', 'article_hosts': ['example.com']}


def item(title='Nouveauté', link='https://example.com/article', date='Thu, 12 Nov 2026 10:00:00 GMT'):
    return f'<item><title>{title}</title><link>{link}</link><pubDate>{date}</pubDate><description>&lt;p&gt;Extrait&lt;/p&gt;&lt;script&gt;secret()&lt;/script&gt;</description></item>'


def rss(entries):
    return '<rss version="2.0"><channel><title>Flux</title>' + entries + '</channel></rss>'


class SourceWatchTests(unittest.TestCase):
    def test_metadata_and_excerpt_are_cleaned(self):
        articles, discarded, outside = watch.parse_feed(rss(item()), SOURCE, NOW, 14)
        self.assertEqual((discarded, outside), (0, 0))
        self.assertEqual(articles[0]['excerpt'], 'Extrait')
        self.assertEqual(articles[0]['published_at'], '2026-11-12T10:00:00+00:00')

    def test_duplicates_fragments_and_old_entries(self):
        body = rss(item() + item(link='https://example.com/article#section') + item(link='/old', date='Thu, 01 Jan 2015 00:00:00 GMT'))
        articles, _, outside = watch.parse_feed(body, SOURCE, NOW, 14)
        self.assertEqual(len(articles), 1)
        self.assertEqual(outside, 1)

    def test_missing_date_and_future_entries(self):
        body = rss(item(date='') + item(link='/future', date='Thu, 12 Nov 2037 00:00:00 GMT'))
        articles, discarded, outside = watch.parse_feed(body, SOURCE, NOW, 14)
        self.assertEqual((articles, discarded, outside), ([], 1, 1))

    def test_external_and_credential_links_are_rejected(self):
        body = rss(item(link='https://elsewhere.test/post') + item(link='https://user:pass@example.com/'))
        articles, discarded, _ = watch.parse_feed(body, SOURCE, NOW, 14)
        self.assertEqual(articles, [])
        self.assertEqual(discarded, 2)

    def test_atom_feed(self):
        body = '<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Atom</title><link href="https://example.com/atom"/><updated>2026-11-12T11:00:00Z</updated><summary>Résumé</summary></entry></feed>'
        articles, _, _ = watch.parse_feed(body, SOURCE, NOW, 14)
        self.assertEqual(articles[0]['url'], 'https://example.com/atom')

    def test_html_fallback_and_entities_are_rejected(self):
        for body in ['<html>Erreur</html>', '<!DOCTYPE rss [<!ENTITY x "test">]><rss><channel/></rss>']:
            with self.assertRaises(ValueError):
                watch.parse_feed(body, SOURCE, NOW, 14)

    def test_partial_failure_is_visible(self):
        other = {**SOURCE, 'id': 'other', 'feed_url': 'https://other.test/rss'}
        def request(url, timeout):
            return {'status': 200, 'error': None, 'body': rss(item())} if url == SOURCE['feed_url'] else {'status': 503, 'error': None, 'body': ''}
        report = watch.collect({'sources': [SOURCE, other]}, request, NOW)
        self.assertEqual(report['state'], 'warning')
        self.assertEqual(len(report['articles']), 1)
        self.assertEqual(report['sources'][1]['state'], 'error')

    def test_all_failed_sources_are_error(self):
        report = watch.collect({'sources': [SOURCE]}, lambda *_: {'status': None, 'error': 'timeout', 'body': ''}, NOW)
        self.assertEqual(report['state'], 'error')

    def test_valid_feed_without_recent_items_is_not_error(self):
        report = watch.collect({'sources': [SOURCE]}, lambda *_: {'status': 200, 'error': None, 'body': rss(item(date='Thu, 01 Jan 2015 00:00:00 GMT'))}, NOW)
        self.assertEqual(report['state'], 'ok')
        self.assertEqual(report['articles'], [])

    def test_markdown_cannot_embed_source_images_or_tags(self):
        value = watch.escaped('![image](https://outside.test/) <script>code</script>')
        self.assertNotIn('![image]', value)
        self.assertNotIn('<script>', value)


if __name__ == '__main__':
    unittest.main()
