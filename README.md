# Google B.C. (Before ChatGPT)

The Google search landing page, with one twist: every search only returns results from before 2023.

Live site: **https://alvations.github.io/google-bc/**

## About

Google B.C. is a one-page, purely client-side emulation of the Google search homepage. When you press Enter, click **Google Search** or **I'm Feeling Lucky**, or search by image, the page builds an ordinary Google URL with the `before:2022-12-31` operator appended and sends your browser there. Google does the crawling, indexing and ranking. The date filter keeps the results to pages Google dates on or before 31 December 2022, one month after ChatGPT was released to the public.

There is no server, no proxy and no tracking. Nothing you type is stored; the page only redirects you to Google.

## How it works

| You do | The page sends you to |
| --- | --- |
| Type `cats` and press Enter | `https://www.google.com/search?q=cats+before%3A2022-12-31` |
| Click **I'm Feeling Lucky** | same URL with `&btnI=1` |
| Click **Images** (top right) with a query typed | same URL with `&tbm=isch` |
| Type your own `before:` date | your date is kept, no second operator is added |

### Search by image

Click the camera icon in the search box (Google Lens):

- **Upload or drag a file**: the image is posted to `https://www.google.com/searchbyimage/upload`, which is Google's own upload endpoint. The `q=before:2022-12-31` field is sent with it.
- **Paste an image link**: your browser goes to `https://www.google.com/searchbyimage?image_url=…&q=before:2022-12-31`.
- **Paste an image from the clipboard** while the dialog is open, or drop an image anywhere on the page.

Google Lens matches images by content, so the date operator applies to the text-based results Lens shows alongside the visual matches, not to the visual matches themselves.

### Links

- **About** (top left) points to this section.
- **How Search works** (top left) is [how-search-works.html](how-search-works.html), an emulation of Google's page of the same name that explains the before-2023 filter.
- **Settings** (bottom right) opens Google's official [Advanced Search](https://www.google.com/advanced_search?hl=en&fg=1&as_q=before%3A2022-12-31) page. The link carries `as_q=before:2022-12-31` so the "all these words" box is pre-filled with the cutoff wherever Google honours that parameter. Note that Google's current advanced-search page ignores every URL parameter (checked September 2026 with `as_q`, `q` and `tbs`), and its "Last update" menu has no custom date range, so you may need to type `before:2022-12-31` into the form yourself.

## Run locally

It is static HTML, so any file server works:

```bash
git clone https://github.com/alvations/google-bc.git
cd google-bc
python3 -m http.server 8000
# open http://localhost:8000/
```

The URL-building logic in `app.js` can be unit-tested without a browser:

```bash
node -e "const a=require('./app.js'); console.log(a.searchUrl('cats'))"
```

## Files

| File | Purpose |
| --- | --- |
| `index.html` | The landing page |
| `style.css` | Google-style layout |
| `app.js` | Builds the Google URLs and handles the search-by-image dialog |
| `how-search-works.html` | "How Search works" page |
| `favicon.svg` | Tab icon |

## Caveats

- The `before:` operator uses the date Google assigns to a page. For undated pages that is Google's best estimate, so an occasional newer page can appear.
- A page published before 2023 and edited later keeps its original date, so it can still show up.
- Google is not affiliated with this project. "Google" and "Google Lens" are trademarks of Google LLC.
