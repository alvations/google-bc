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
| Click **I'm Feeling Lucky** | the Wayback Machine capture of Google's first result, from on or before 31 Dec 2022 (see below) |
| Click **Images** (top right) | Images mode: the same page, and searches go to Google Images with `before:2022-12-31` plus a custom date range ending 31 Dec 2022 (`tbm=isch&tbs=cdr:1,cd_min:1/1/1990,cd_max:12/31/2022`). With a query already typed, Images searches it straight away. |
| Type your own `before:` date | your date is kept, no second operator is added |

### I'm Feeling Lucky (Wayback Machine)

A browser cannot see where Google's lucky redirect lands (it is cross-origin), so Lucky goes through a small service in [`resolver/`](resolver/) instead:

1. The page sends the query to `https://google-bc-lucky-505312891007.us-central1.run.app/lucky?q=…`.
2. The service collects candidate results, pooled from these sources in order: the official Google Custom Search JSON API if `CSE_KEY` and `CSE_CX` are set (it supports a real date filter and has 100 free queries a day); otherwise Google's own lucky redirect with the `before:2022-12-31` operator (this works from residential IPs, but cloud IPs get Google's captcha page); otherwise Bing's web results via its RSS feed.
3. For each candidate in order it asks the Wayback Machine (CDX API, then the availability API) for the last capture on or before 31 December 2022, and picks the first candidate that has one.
4. It redirects you to `https://web.archive.org/web/<timestamp>/<url>`. If no candidate has a capture before the cutoff, it uses the first candidate with the cutoff timestamp and Wayback picks the nearest capture it has. If nothing can be resolved at all, you get Google's own lucky redirect.

Add `&format=json` to the service URL to see the decision instead of being redirected. The service is stdlib-only Python, keeps a small in-memory cache, and runs on Cloud Run scaled to zero. Deploy your own with:

```bash
cd resolver
gcloud run deploy google-bc-lucky --source . --region us-central1 --allow-unauthenticated \
  --min-instances 0 --max-instances 2 --memory 256Mi
```

then point `LUCKY_RESOLVER` in `app.js` at the URL it prints. Set it to an empty string to fall back to Google's plain lucky redirect.

To use Google's own ranking from a cloud host, create a Programmable Search Engine that searches the whole web at https://programmablesearchengine.google.com/, enable the Custom Search API in your project, and deploy with `--set-env-vars CSE_KEY=<api key>,CSE_CX=<engine id>`.

### Search by image

Click the camera icon in the search box (Google Lens):

- **Upload or drag a file**: the image is posted to `https://www.google.com/searchbyimage/upload`, which is Google's own upload endpoint. The `q=before:2022-12-31` field is sent with it.
- **Paste an image link**: your browser goes to `https://www.google.com/searchbyimage?image_url=…&q=before:2022-12-31`.
- **Paste an image from the clipboard** while the dialog is open, or drop an image anywhere on the page.

Google Lens matches images by content, so the date operator applies to the text-based results Lens shows alongside the visual matches, not to the visual matches themselves.

### Links

- **About** (top left) points to this section.
- **How Search works** (top left) is [how-search-works.html](how-search-works.html), an emulation of Google's page of the same name that explains the before-2023 filter.
- There is no Settings link. Google's Advanced Search page ignores every URL parameter (checked September 2026 with `as_q`, `q` and `tbs`), so it cannot be pre-filled with the cutoff.

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
| `resolver/main.py` | I'm Feeling Lucky service: Google first result → Wayback capture before 2023 |

## Caveats

- The `before:` operator uses the date Google assigns to a page. For undated pages that is Google's best estimate, so an occasional newer page can appear.
- A page published before 2023 and edited later keeps its original date, so it can still show up.
- Google is not affiliated with this project. "Google" and "Google Lens" are trademarks of Google LLC.
