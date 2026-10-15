from pathlib import Path
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]


class ForkPagesTest(unittest.TestCase):
    def test_lockfile_checksums_are_complete(self):
        text = (ROOT / 'docs/Gemfile.lock').read_text()
        checksums = text.split('CHECKSUMS\n', 1)[1].split('\n\n', 1)[0]
        for line in checksums.splitlines():
            with self.subTest(entry=line):
                self.assertRegex(line, r' sha256=[0-9a-f]{64}$')

    def test_site_identity(self):
        config = (ROOT / 'docs/_config.yml').read_text()
        self.assertIn('url: "https://ginizi.github.io"', config)
        self.assertIn('baseurl: "/elektroid"', config)
        self.assertIn('  - index.md', config)

    def test_landing_page(self):
        page = (ROOT / 'docs/fork-home.md').read_text()
        self.assertIn('permalink: /', page)
        self.assertIn('Digitakt I', page)
        self.assertIn('https://github.com/ginizi/elektroid', page)
        self.assertIn('https://github.com/dagargo/elektroid', page)
        self.assertIn('./scripts/dt-build-banks', page)
        self.assertIn('--dry-run', page)

    def test_sitemap(self):
        text = (ROOT / 'docs/sitemap.xml').read_text()
        tree = ET.fromstring(text.split('---', 2)[-1])
        ns = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        self.assertIn('{{ site.url }}{{ site.baseurl }}/',
                      [node.text for node in tree.findall('s:url/s:loc', ns)])

    def test_deployment(self):
        workflow = (ROOT / '.github/workflows/pages.yml').read_text()
        self.assertIn('deploy-pages@', workflow)
        self.assertIn('bundle exec jekyll build', workflow)
        self.assertIn('github.repository == \'ginizi/elektroid\'', workflow)
