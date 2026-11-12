"""Public, read-only website checks. Python standard library only."""

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

MAX_BYTES = 2_000_000


def origin(url):
    parsed = urllib.parse.urlsplit(url)
    return parsed.scheme, parsed.hostname, parsed.port


def internal_url(base, reference):
    url, _ = urllib.parse.urldefrag(urllib.parse.urljoin(base, reference))
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or origin(url) != origin(base):
        return None
    if parsed.username or parsed.password:
        return None
    return url


class SameOriginRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, base):
        self.base = base

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not internal_url(self.base, newurl):
            raise urllib.error.URLError('Redirection hors du site ou sans HTTPS')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = set()
        self.tags = set()
        self.meta_csp = ''

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag)
        attrs = dict(attrs)
        if tag == 'a' and attrs.get('href'):
            self.links.add(attrs['href'])
        if tag == 'meta' and attrs.get('http-equiv', '').lower() == 'content-security-policy':
            self.meta_csp = attrs.get('content', '')


def fetch(url, timeout):
    """Retry transient errors once, retaining TLS verification and proxy settings."""
    opener = urllib.request.build_opener(SameOriginRedirect(url))
    for attempt in range(2):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'KoralyaMonitor/1.0'})
            with opener.open(request, timeout=timeout) as response:
                body = response.read(MAX_BYTES + 1)
                if len(body) > MAX_BYTES:
                    return {'status': response.status, 'headers': {}, 'body': '', 'error': 'Réponse trop volumineuse'}
                return {'status': response.status, 'headers': dict(response.headers.items()),
                        'body': body.decode('utf-8', errors='replace'), 'error': None}
        except urllib.error.HTTPError as exc:
            result = {'status': exc.code, 'headers': {}, 'body': '', 'error': None}
            exc.close()
            if exc.code != 429 and exc.code < 500:
                return result
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            result = {'status': None, 'headers': {}, 'body': '', 'error': 'Connexion, TLS, délai ou redirection refusée'}
        if attempt == 0:
            time.sleep(2)
    return result


def inspect_page(path, response):
    findings = []
    page = Page()
    if response['error'] or response['status'] != 200:
        findings.append({'severity': 'error', 'path': path,
                         'message': response['error'] or f"HTTP {response['status']}"})
        return findings, page
    page.feed(response['body'])
    headers = {key.lower(): value for key, value in response['headers'].items()}
    if 'html' not in page.tags or 'title' not in page.tags or 'main' not in page.tags:
        findings.append({'severity': 'error', 'path': path, 'message': 'Structure HTML attendue absente'})
    checks = {
        'content-security-policy': lambda v: bool(v.strip()),
        'strict-transport-security': lambda v: bool(re.search(r'max-age\s*=\s*[1-9][0-9]*', v, re.I)),
        'x-content-type-options': lambda v: v.lower().strip() == 'nosniff',
        'referrer-policy': lambda v: bool(v.strip()),
        'permissions-policy': lambda v: bool(v.strip()),
    }
    for name, valid in checks.items():
        if not valid(headers.get(name, '')):
            findings.append({'severity': 'warning', 'path': path,
                             'message': f'En-tête absent ou à examiner : {name}'})
    csp = headers.get('content-security-policy', '')
    if 'frame-ancestors' not in csp.lower() and headers.get('x-frame-options', '').upper() not in ('DENY', 'SAMEORIGIN'):
        findings.append({'severity': 'warning', 'path': path, 'message': 'Protection contre l’intégration en cadre à examiner'})
    if page.meta_csp and not csp:
        findings.append({'severity': 'info', 'path': path,
                         'message': 'CSP en balise HTML présente ; vérifier aussi les scripts et les ressources'})
    return findings, page


def run(config, request=fetch):
    base = config['base_url'].rstrip('/')
    if not internal_url(base, base) or urllib.parse.urlsplit(base).path:
        raise ValueError('base_url doit être une origine HTTPS sans chemin')
    timeout = config.get('timeout_seconds', 15)
    report = {'checked_at': datetime.now(timezone.utc).isoformat(), 'site': base,
              'checks': [], 'findings': [], 'scope': 'Contrôles publics en lecture seule ; aucun audit des accès, dépendances ou secrets.'}
    cache = {}

    def get(path):
        url = internal_url(base + '/', path)
        if not url:
            raise ValueError('Adresse de contrôle hors du site')
        if url not in cache:
            cache[url] = request(url, timeout)
            report['checks'].append({'path': urllib.parse.urlsplit(url).path,
                                     'status': cache[url]['status'], 'error': cache[url]['error']})
        return cache[url]

    links = set()
    for path in config['pages']:
        response = get(path)
        findings, page = inspect_page(path, response)
        report['findings'].extend(findings)
        for href in page.links:
            link = internal_url(base + path, href)
            if link:
                links.add(link)

    for url in sorted(links)[:config.get('max_internal_links', 35)]:
        response = get(url)
        if response['error'] or response['status'] != 200:
            report['findings'].append({'severity': 'error', 'path': urllib.parse.urlsplit(url).path,
                                       'message': 'Lien interne inaccessible'})

    sitemap = get('/sitemap.xml')
    try:
        if sitemap['status'] != 200 or sitemap['error']:
            raise ValueError()
        root = ET.fromstring(sitemap['body'])
        namespace = '{http://www.sitemaps.org/schemas/sitemap/0.9}'
        locations = [node.text for node in root.iter(namespace + 'loc')]
        if root.tag != namespace + 'urlset' or not locations:
            raise ValueError()
        if any(not location or not internal_url(base + '/', location) for location in locations):
            raise ValueError()
    except (ET.ParseError, ValueError):
        report['findings'].append({'severity': 'error', 'path': '/sitemap.xml', 'message': 'Sitemap indisponible, invalide ou hors du site'})

    robots = get('/robots.txt')
    if robots['error'] or robots['status'] != 200 or 'sitemap:' not in robots['body'].lower() or '<html' in robots['body'].lower():
        report['findings'].append({'severity': 'warning', 'path': '/robots.txt', 'message': 'robots.txt ou référence au sitemap à examiner'})

    contact = get('/api/contact/config')
    try:
        data = json.loads(contact['body']) if contact['status'] == 200 else {}
        available = not contact['error'] and data.get('available') is True and bool(data.get('siteKey'))
    except (ValueError, AttributeError):
        available = False
    if not available:
        report['findings'].append({'severity': 'error' if config.get('contact_direct_required') else 'info',
                                   'path': '/api/contact/config', 'message': 'Envoi direct non confirmé ; parcours WhatsApp/e-mail à conserver'})

    severities = {finding['severity'] for finding in report['findings']}
    report['state'] = 'error' if 'error' in severities else 'warning' if 'warning' in severities else 'ok'
    return report


def markdown(report):
    labels = {'ok': 'OK', 'warning': 'Points à examiner', 'error': 'Échec'}
    lines = ['# Contrôle Koralya Studio', '', f"Date : {report['checked_at']}",
             f"Site : {report['site']}", f"État : **{labels[report['state']]}**", '',
             '## Pages et ressources', '', '| Chemin | HTTP |', '|---|---|']
    for check in report['checks']:
        lines.append(f"| {check['path']} | {check['status'] or 'Erreur réseau'} |")
    lines += ['', '## Résultats', '']
    for finding in report['findings']:
        lines.append(f"- **{finding['severity']}** `{finding['path']}` : {finding['message']}")
    if not report['findings']:
        lines.append('Aucune anomalie dans les contrôles exécutés.')
    lines += ['', report['scope'], '', 'Les avertissements sur les en-têtes ne prouvent pas une compromission.', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='automation/monitor.json')
    parser.add_argument('--output', default='reports')
    args = parser.parse_args()
    report = run(json.loads(Path(args.config).read_text()))
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    (output / 'monitor.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    (output / 'monitor.md').write_text(markdown(report))
    print(f"État : {report['state']} ; {len(report['checks'])} ressources contrôlées ; rapport : {output / 'monitor.md'}")
    return 1 if report['state'] == 'error' else 0


if __name__ == '__main__':
    sys.exit(main())
