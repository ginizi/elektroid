# Publish the fork website

The landing page is `docs/fork-home.md`; `docs/index.md` remains an unchanged source for README generation. The website configuration targets the ginizi fork, not the upstream site.

## GitHub Pages

1. Review the website branch and merge it into `master` only after approval.
2. In the fork's **Settings → Pages → Build and deployment**, select **GitHub Actions** as the source.
3. Push the approved changes to `origin/master`.
4. Open **Actions → Deploy fork website** and check the build and deployment results; use **Run workflow** on `master` if necessary.
5. Verify `https://ginizi.github.io/elektroid/` and `https://ginizi.github.io/elektroid/sitemap.xml` in a browser.

The workflow runs only in `ginizi/elektroid`, with deployment permissions limited to the deploy job. Enabling Pages or pushing the branch is not part of preparing the site locally.

## Google indexing

1. Add a **URL-prefix** property for `https://ginizi.github.io/elektroid/` in Google Search Console.
2. Verify ownership using the HTML file method: place the exact downloaded verification file in `docs/`, without adding Jekyll front matter, then publish it through the same approved workflow.
3. Confirm that the verification file is accessible at the URL Google specifies, then complete verification.
4. Submit `https://ginizi.github.io/elektroid/sitemap.xml`.
5. Inspect the homepage URL and request indexing.

Indexing and search ranking are not guaranteed or immediate. Keep the verification file published and link to the website from the repository's About section and relevant community posts.
The project-level `robots.txt` is informational: crawlers use the host-root `/robots.txt`, not `/elektroid/robots.txt`; do not rely on it for indexing controls.
