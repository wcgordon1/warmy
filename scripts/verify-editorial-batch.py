#!/usr/bin/env python3
"""Verify built or served editorial pages and their public discovery surfaces."""
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = sys.argv[1].rstrip('/') if len(sys.argv) > 1 else None
POSTS = [p for p in sorted((ROOT/'src/content/posts').glob('*.md')) if 'editorial: true' in p.read_text()]
assert len(POSTS) == 5

def read(path):
    if ORIGIN:
        with urlopen(ORIGIN+path, timeout=30) as response:
            assert response.status == 200, path
            assert 'noindex' not in response.headers.get('X-Robots-Tag', '').lower(), path
            return response.read().decode()
    p = ROOT/'dist'/path.lstrip('/')
    if p.is_dir():
        p = p/'index.html'
    return p.read_text()

class Page(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.nodes, self.stack, self.visible, self.schemas, self.h1, self.title = [], [], [], [], [], []
        self.json_text = None
        self.feed(source)
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        node = dict(tag=tag, **attrs)
        if tag == 'a':
            node['cta'] = next((a.get('id') for _,a in reversed(self.stack) if 'guide-cta' in a.get('class','').split()), None)
        self.nodes.append(node)
        if tag == 'script' and attrs.get('type') == 'application/ld+json':
            self.json_text = ''
        if tag not in {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}:
            self.stack.append((tag,attrs))
    def handle_endtag(self, tag):
        if tag == 'script' and self.json_text is not None:
            self.schemas.append(json.loads(self.json_text)); self.json_text = None
        for i in range(len(self.stack)-1,-1,-1):
            if self.stack[i][0] == tag:
                self.stack = self.stack[:i]; break
    def handle_data(self, text):
        if self.json_text is not None: self.json_text += text
        tags = [t for t,_ in self.stack]
        if not any(t in tags for t in ['script','style']): self.visible.append(text)
        if 'h1' in tags: self.h1.append(text)
        if 'title' in tags: self.title.append(text)
    def select(self, tag, **attrs):
        return [n for n in self.nodes if n['tag']==tag and all(n.get(k)==v for k,v in attrs.items())]

for post in POSTS:
    slug = post.stem; path = '/posts/'+slug+'/'
    frontmatter = post.read_text().split('---',2)[1]
    data = {k:json.loads(v.strip()) for k,v in (line.split(':',1) for line in frontmatter.strip().splitlines())}
    page = Page(read(path))
    visible = re.sub(r'\s+', ' ', ' '.join(page.visible))
    assert len(page.select('h1')) == 1 and ''.join(page.h1) == data['title'], path
    assert ''.join(page.title) == data['title']+' | Warm Websites'
    assert page.select('link', rel='canonical')[0]['href'] == 'https://warmwebsites.com'+path
    assert not any('noindex' in n.get('content','').lower() for n in page.select('meta', name='robots'))
    assert len(page.select('meta', **{'property':'og:type'})) == 1
    assert page.select('meta', **{'property':'og:type'})[0]['content'] == 'article'
    assert page.select('meta', **{'property':'og:image'})[0]['content'] == 'https://warmwebsites.com'+data['cover']['image']
    assert page.select('a', href=data['author']['url'])
    assert 'By Will Gordon' in visible and 'Disclosure:' in visible
    assert len(page.select('time')) == 2
    assert len(page.select('table')) == 2
    assert len(page.select('div', tabindex='0', role='region')) == 2
    for position in ['beginning','middle','end']:
        links = [n for n in page.select('a') if n.get('cta')=='cta-'+position]
        assert links,(path,position)
        for link in links:
            query=parse_qs(urlparse(link['href']).query)
            assert query.get('utm_source')==['warmwebsites.com']
            assert query.get('utm_campaign')==[slug]
            assert query.get('utm_content',[None])[0].startswith(position)
            assert link.get('rel')=='sponsored'
    assert visible.index(data['faq'][-1]['answer']) < visible.index(data['ctaEnd']['heading'])
    faq = next(s for s in page.schemas if s.get('@type')=='FAQPage')['mainEntity']
    assert len(faq)==len(data['faq'])==6
    for actual,expected in zip(faq,data['faq']):
        assert actual['name']==expected['question']
        assert actual['acceptedAnswer']['text']==expected['answer']
        assert expected['question'] in visible and expected['answer'] in visible
    article=next(s for s in page.schemas if s.get('@type')=='BlogPosting')
    assert article['author']['@type']=='Person' and article['author']['name']=='Will Gordon'
    assert article['datePublished']==article['dateModified']=='2026-10-23T00:00:00.000Z'
    for image in page.select('img'):
        assert image.get('alt')
        if ORIGIN:
            with urlopen(ORIGIN+image['src'],timeout=30) as response:
                assert response.status==200 and response.headers.get('Content-Type','').startswith('image/')
        else:
            assert (ROOT/'dist'/image['src'].lstrip('/')).exists()
    if slug=='best-sales-job-boards-web-agencies':
        assert 'https://mcp.accountexecutivejobs.com/mcp' in visible
        assert 'Developer mode' in visible
        assert any('/affiliate' in n.get('href','') for n in page.select('a'))
    print('PASS',path,'canonical, metadata, author, dates, three CTAs, six FAQs, two tables, images')

for path in ['/','/rss.xml','/search-index.json','/sitemap-0.xml','/llms.txt']:
    text=read(path)
    assert all(post.stem in text for post in POSTS),path
    print('PASS discovery:',path)
assert len(json.loads(read('/search-index.json')))>=13
assert read('/rss.xml').count('<item>')>=13
assert 'Sitemap: https://warmwebsites.com/sitemap-index.xml' in read('/robots.txt')
for path in ['/about','/search','/posts/best-startup-lead-databases','/posts/how-to-practice-wedding-vows','/404.html']:
    read(path);print('PASS existing route:',path)
if not ORIGIN:
    baseline=Path('/tmp/warm-baseline-paths.txt')
    if baseline.exists():
        paths=baseline.read_text().splitlines();assert all((ROOT/p).exists() for p in paths)
        print('PASS baseline HTML paths:',len(paths))
