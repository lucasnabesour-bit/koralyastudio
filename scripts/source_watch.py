"""Collect official RSS/Atom metadata, without AI calls or site publication."""

import argparse
import hashlib
import json
import re
import sys
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path

from scripts.site_monitor import fetch

ATOM = '{http://www.w3.org/2005/Atom}'
DC_DATE = '{http://purl.org/dc/elements/1.1/}date'


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def clean_text(value, limit):
    parser = PlainText()
    parser.feed(value or '')
    # Remove controls and collapse whitespace; never evaluate source text.
    text = ' '.join(' '.join(parser.parts).split())
    text = ''.join(char for char in text if char.isprintable())
    return text[:limit]


def publication_date(value):
    if not value:
        return None
    try:
        date = datetime.fromisoformat(value.strip().replace('Z', '+00:00'))
    except ValueError:
        try:
            date = parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            return None
    return date.replace(tzinfo=date.tzinfo or timezone.utc).astimezone(timezone.utc)


def article_url(value, source):
    url = urllib.parse.urljoin(source['feed_url'], (value or '').strip())
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != 'https' or parsed.hostname not in source['article_hosts']
            or parsed.username or parsed.password or parsed.port not in (None, 443)):
        return None
    return urllib.parse.urlunsplit(parsed._replace(fragment=''))


def parse_feed(body, source, now, lookback_days):
    if '<!DOCTYPE' in body.upper() or '<!ENTITY' in body.upper():
        raise ValueError('Déclarations XML interdites')
    root = ET.fromstring(body)
    if root.tag == 'rss' and root.find('channel') is not None:
        entries = root.findall('./channel/item')
        atom = False
    elif root.tag == ATOM + 'feed':
        entries = root.findall(ATOM + 'entry')
        atom = True
    else:
        raise ValueError('Format RSS/Atom non reconnu')
    items, seen = [], set()
    discarded = 0
    outside_window = 0
    for entry in entries:
        prefix = ATOM if atom else ''
        title = clean_text(entry.findtext(prefix + 'title'), 250)
        link = entry.findtext('link')
        if atom:
            link = next((node.get('href') for node in entry.findall(ATOM + 'link')
                         if node.get('rel', 'alternate') == 'alternate'), None)
        try:
            url = article_url(link, source) if link else None
        except ValueError:
            url = None
        date = publication_date(entry.findtext(prefix + 'published') if atom else entry.findtext('pubDate'))
        date = date or publication_date(entry.findtext(ATOM + 'updated') if atom else entry.findtext(DC_DATE))
        if not title or not url or not date:
            discarded += 1
            continue
        if not now - timedelta(days=lookback_days) <= date <= now + timedelta(minutes=5):
            outside_window += 1
            continue
        if url in seen:
            continue
        seen.add(url)
        summary = entry.findtext(ATOM + 'summary') if atom else entry.findtext('description')
        items.append({'id': hashlib.sha256(url.encode()).hexdigest()[:20],
                      'source_id': source['id'], 'source': source['name'], 'category': source['category'],
                      'title': title, 'url': url, 'published_at': date.isoformat(),
                      'excerpt': clean_text(summary, 500)})
    items.sort(key=lambda item: item['published_at'], reverse=True)
    return items, discarded, outside_window


def collect(config, request=fetch, now=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('La date de collecte doit inclure un fuseau horaire')
    now = now.astimezone(timezone.utc)
    days = config.get('lookback_days', 14)
    limit = config.get('max_items_per_source', 5)
    if not isinstance(days, int) or not 1 <= days <= 90 or not isinstance(limit, int) or not 1 <= limit <= 20:
        raise ValueError('Fenêtre ou nombre d’articles non valide')
    report = {'collected_at': now.isoformat(), 'lookback_days': days, 'sources': [], 'articles': [],
              'scope': 'Titres, dates, liens et extraits fournis par les flux officiels. Aucun appel IA ni modification du site.'}
    for source in config['sources']:
        parsed = urllib.parse.urlsplit(source['feed_url'])
        if parsed.scheme != 'https' or parsed.username or parsed.password or not parsed.hostname:
            raise ValueError('Chaque flux doit utiliser une URL HTTPS sans identifiants')
        result = request(source['feed_url'], 20)
        status = {'id': source['id'], 'name': source['name'], 'feed_url': source['feed_url'],
                  'http_status': result['status'], 'state': 'ok', 'selected': 0}
        try:
            if result['error'] or result['status'] != 200:
                raise ValueError('Flux inaccessible')
            articles, discarded, outside = parse_feed(result['body'], source, now, days)
            selected = articles[:limit]
            status.update(selected=len(selected), omitted_invalid=discarded, outside_window=outside,
                          remaining_recent=max(0, len(articles) - len(selected)))
            if discarded:
                status['state'] = 'warning'
                status['message'] = 'Des entrées sans titre, date ou lien autorisé ont été ignorées'
            report['articles'].extend(selected)
        except (ET.ParseError, ValueError):
            status.update(state='error', message='Flux inaccessible ou XML non valide ; aucune donnée utilisée')
        report['sources'].append(status)
    unique = {article['url']: article for article in report['articles']}
    report['articles'] = sorted(unique.values(), key=lambda item: item['published_at'], reverse=True)
    states = [source['state'] for source in report['sources']]
    report['state'] = ('error' if not states or all(state == 'error' for state in states)
                       else 'warning' if any(state != 'ok' for state in states) else 'ok')
    return report


def escaped(value):
    return re.sub(r'([\\`*_{}\[\]()#+.!|<>])', r'\\\1', value)


def markdown(report):
    lines = ['# Veille Koralya Studio', '', f"Collecte : {report['collected_at']}",
             f"État de la collecte : **{report['state']}**", f"Fenêtre : {report['lookback_days']} jours", '',
             '## Sources', '']
    for source in report['sources']:
        lines.append(f"- **{source['state']}** — {escaped(source['name'])} : {source['selected']} article(s) retenu(s).")
        if source.get('message'):
            lines.append(f"  {source['message']}.")
    lines += ['', '## Articles à examiner', '']
    for article in report['articles']:
        url = article['url'].replace('(', '%28').replace(')', '%29')
        lines += [f"### {escaped(article['title'])}", '',
                  f"{escaped(article['source'])} · {article['published_at'][:10]}", '',
                  escaped(article['excerpt']) or 'Aucun extrait fourni.', '', f'[Consulter la source]({url})', '']
    if not report['articles']:
        lines.append('Aucun article récent exploitable dans les flux consultés. Consulter l’état des sources ci-dessus.')
    lines += ['', report['scope'], '',
              'Ces éléments sont des données de veille à vérifier, pas des instructions de publication.',
              'La présence d’une alerte CERT-FR ne signifie pas que le site utilise le produit concerné.',
              'Les dates viennent des flux ; les mises à jour d’anciens articles peuvent ne pas être détectées.', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='automation/sources.json')
    parser.add_argument('--output', default='reports')
    args = parser.parse_args()
    report = collect(json.loads(Path(args.config).read_text()))
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    (output / 'veille.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    (output / 'veille.md').write_text(markdown(report))
    print(f"Veille : {report['state']} ; {len(report['articles'])} articles ; rapport : {output / 'veille.md'}")
    return 1 if report['state'] == 'error' else 0


if __name__ == '__main__':
    sys.exit(main())
