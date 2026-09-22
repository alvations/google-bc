/* Google B.C. (Before ChatGPT)
 * Purely client-side: every search is turned into a normal Google URL with
 * "before:2022-12-31" appended, then the browser is sent there. */
(function () {
  'use strict';

  var CUTOFF = '2022-12-31';
  var OPERATOR = 'before:' + CUTOFF;
  var GOOGLE = 'https://www.google.com';

  function enc(s) {
    return encodeURIComponent(s).replace(/%20/g, '+');
  }

  /* Append the cutoff unless the user already wrote their own before: date. */
  function withCutoff(q) {
    q = (q || '').trim().replace(/\s+/g, ' ');
    if (/(^|\s)before:\s*\d{4}(-\d{1,2}){0,2}(\s|$)/i.test(q)) return q;
    return q ? q + ' ' + OPERATOR : OPERATOR;
  }

  /* Google's own custom-date-range filter (Tools > Any time > Custom range),
   * used as a second fence for image results. */
  var TBS_BEFORE = 'cdr:1,cd_min:1/1/1990,cd_max:12/31/2022';

  function searchUrl(q, opts) {
    opts = opts || {};
    var url = GOOGLE + '/search?q=' + enc(withCutoff(q));
    if (opts.images) url += '&tbm=isch&tbs=' + encodeURIComponent(TBS_BEFORE);
    return url;
  }

  /* Reverse image search by URL. Google forwards the q= text into Lens. */
  function imageUrlSearchUrl(imageUrl) {
    return GOOGLE + '/searchbyimage?image_url=' + encodeURIComponent(imageUrl) +
      '&q=' + encodeURIComponent(OPERATOR) + '&sbisrc=google-bc';
  }

  var api = {
    CUTOFF: CUTOFF,
    OPERATOR: OPERATOR,
    withCutoff: withCutoff,
    searchUrl: searchUrl,
    imageUrlSearchUrl: imageUrlSearchUrl
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof document === 'undefined') return;

  function $(id) { return document.getElementById(id); }
  function go(url) { window.location.href = url; }

  var form = $('search-form');
  var q = $('q');

  /* "?tbm=isch" turns the page into Google Images B.C.: same box, image results. */
  var imagesMode = /(^|[?&])tbm=isch(&|$)/.test(window.location.search);
  var imagesLink = $('images-link');
  if (imagesMode) {
    $('mode-label').hidden = false;
    document.title = 'Google Images B.C.';
    imagesLink.textContent = 'All';
    imagesLink.setAttribute('href', './');
    $('btn-search').textContent = 'Search images';
    $('notice').innerHTML = 'Every image search is sent to Google Images with <code>before:2022-12-31</code> ' +
      'and a custom date range ending 31 Dec 2022, so all results come from before 2023.';
  }

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    go(searchUrl(q.value, { images: imagesMode }));
  });

  /* Images with a query already typed searches it straight away;
   * with an empty box it switches this page into Images mode. */
  imagesLink.addEventListener('click', function (e) {
    if (imagesMode || !q.value.trim()) return;
    e.preventDefault();
    go(searchUrl(q.value, { images: true }));
  });

  /* Search by image */
  var overlay = $('lens-overlay');
  var fileInput = $('file-input');
  var uploadForm = $('upload-form');
  var dropZone = $('drop-zone');
  var urlInput = $('image-url');

  function openLens() {
    overlay.hidden = false;
    urlInput.focus();
  }
  function closeLens() {
    overlay.hidden = true;
    q.focus();
  }

  $('lens-btn').addEventListener('click', openLens);
  if (window.location.hash === '#lens') openLens();
  $('lens-close').addEventListener('click', closeLens);
  overlay.addEventListener('click', function (e) { if (e.target === overlay) closeLens(); });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && !overlay.hidden) closeLens();
  });

  function submitFiles(files) {
    if (!files || !files.length) return false;
    var file = files[0];
    if (file.type && file.type.indexOf('image/') !== 0) return false;
    try {
      if (fileInput.files !== files) {
        var dt = new DataTransfer();
        dt.items.add(file);
        fileInput.files = dt.files;
      }
    } catch (err) {
      return false;
    }
    uploadForm.submit();
    return true;
  }

  fileInput.addEventListener('change', function () { submitFiles(fileInput.files); });

  $('url-form').addEventListener('submit', function (e) {
    e.preventDefault();
    var url = urlInput.value.trim();
    if (!url) return;
    go(imageUrlSearchUrl(url));
  });

  /* Drag and drop: a local file uploads, an image dragged from another tab uses its URL. */
  ['dragenter', 'dragover'].forEach(function (name) {
    dropZone.addEventListener(name, function (e) {
      e.preventDefault();
      dropZone.classList.add('hover');
    });
  });
  ['dragleave', 'drop'].forEach(function (name) {
    dropZone.addEventListener(name, function () { dropZone.classList.remove('hover'); });
  });
  dropZone.addEventListener('drop', function (e) {
    e.preventDefault();
    var dt = e.dataTransfer;
    if (dt.files && dt.files.length && submitFiles(dt.files)) return;
    var uri = dt.getData('text/uri-list') || dt.getData('text/plain');
    if (uri && /^https?:\/\//i.test(uri.trim())) go(imageUrlSearchUrl(uri.trim().split('\n')[0]));
  });

  /* Pasting an image (or an image link) while the dialog is open searches it. */
  document.addEventListener('paste', function (e) {
    if (overlay.hidden) return;
    var items = e.clipboardData && e.clipboardData.files;
    if (items && items.length && submitFiles(items)) { e.preventDefault(); return; }
    var text = e.clipboardData && e.clipboardData.getData('text');
    if (text && /^https?:\/\//i.test(text.trim()) && document.activeElement !== urlInput) {
      e.preventDefault();
      go(imageUrlSearchUrl(text.trim()));
    }
  });

  /* Dropping an image anywhere on the page opens the dialog first. */
  document.addEventListener('dragover', function (e) {
    if (overlay.hidden && e.dataTransfer && e.dataTransfer.types.indexOf('Files') !== -1) {
      e.preventDefault();
      openLens();
    }
  });
  document.addEventListener('drop', function (e) {
    if (e.target === dropZone || dropZone.contains(e.target)) return;
    e.preventDefault();
    if (e.dataTransfer && e.dataTransfer.files.length) submitFiles(e.dataTransfer.files);
  });
})();
