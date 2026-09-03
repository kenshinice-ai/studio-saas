/* Studio Admin console script — externalised verbatim from
 * studio-admin.html in v10.11.0. Classic script, deliberately NOT a
 * module or IIFE: its top-level const/let/function declarations land in
 * the global lexical environment exactly as the inline block's did, so
 * the small early-boot inline script and this file keep seeing each
 * other unchanged. Loaded from the same position in the document.
 */
    const $ = (id) => document.getElementById(id);
    const text = (value) => value === null || value === undefined || value === '' ? '-' : String(value);
    const esc = window.StudioSaaS.esc;
    const currentTenantSlug = () => $('tenantSlug').value.trim().toLowerCase();
    const pathTenantSlug = () => {
      const match = location.pathname.match(/^\/([^/]+)\/studio-admin\/?$/);
      return match ? decodeURIComponent(match[1]).toLowerCase() : '';
    };

    /* 2-1: the eight themes and eight industries all carry a Chinese name, and
       the brand builder printed only `label`, so a Chinese-speaking owner chose
       between "Atelier Clay" and "Rehearsal Rose". These read the localised
       field when the console is in Chinese and fall back to English, never the
       other way round — an untranslated preset shows its English name rather
       than nothing. */
    const adminIsZh = () => window.AdminI18n?.language === 'zh';
    const localisedField = (item, enKey, zhKey) => {
      if (!item) return '';
      const en = String(item[enKey] ?? '').trim();
      const zh = String(item[zhKey] ?? '').trim();
      return (adminIsZh() ? (zh || en) : (en || zh));
    };
    const styleName = (style) => localisedField(style, 'label', 'labelZh') || 'Theme';
    const styleDescription = (style) => {
      const copy = localisedField(style, 'description', 'descriptionZh');
      /* Legacy/cached responses carry only the English sentence; the admin
         dictionary still has it, so translate rather than show English. */
      return copy && adminIsZh() && !String(style?.descriptionZh || '').trim()
        ? (window.AdminI18n?.translate(copy) || copy)
        : copy;
    };
    const harmonyName = (style) => {
      const pair = style?.harmonyLabel;
      if (pair && typeof pair === 'object') return localisedField(pair, 'en', 'zh');
      const raw = String(style?.harmony || '');
      return raw ? (window.AdminI18n?.translate(raw) || raw) : '';
    };
    const industryName = (preset) => localisedField(preset, 'label', 'labelZh');
    const industrySlogan = (preset) => localisedField(preset, 'slogan', 'sloganZh');
    const industryStarterCourse = (preset) => {
      const first = preset?.operationalTemplate?.starterCourses?.[0];
      if (!first) return '';
      return localisedField(first, 'en', 'zh');
    };

    /* Shown only until /v1/.../industry-presets answers. Every string here is a
       copy of the `general` preset in backend/studiosaas/presets.py and is
       asserted against it by tests/test_preset_copy.py, so the placeholder
       cannot quietly become a second version of the copy. */
    let INDUSTRY_PRESETS = {
      general: {
        label: 'General', labelZh: '通用', slogan: 'A learning path that fits every student.',
        sloganZh: '适合每个学员的成长路径。',
        portalLabel: 'Student Portal',
        registerIntro: 'Interests, experience and goals, then the studio will suggest a class and a time.',
        registerIntroZh: '兴趣方向、当前经验与学习目标，之后工作室会推荐合适的课程与时间。',
        registrationTitle: 'Tell us about the student', registrationTitleZh: '告诉我们学员的兴趣与学习目标',
        localizedCopy: {}, visualTheme: {}, registrationProfile: { title: 'Tell us about the student', fields: [] }
      }
    };
    let VISUAL_STYLE_PRESETS = {};

    /* What the theme controls show before /v1/industry-presets answers, and if
     * it never does.
     *
     * These used to be twenty separate `|| '#2563eb'` literals scattered
     * through the file, and they were a FIFTH palette: blue #2563eb on cold
     * slate #64748b, left over from the console's own Tailwind era. A studio
     * whose preset request failed saw six colour pickers pre-filled with a
     * scheme that exists nowhere in the product, and if it saved, that is what
     * got published.
     *
     * One object, taken from the default style's light mode
     * (vintage-press — presets.py DEFAULT_STYLE_ID), so the degraded state is
     * the same palette an unbranded page already renders.
     * test_studio_console.py asserts these values against style_theme().
     */
    const FALLBACK_THEME = {
      background_color: '#F3EFEA',
      background_alt_color: '#EAE3DB',
      panel_color: '#FDFDFD',
      text_color: '#221E1A',
      text_soft_color: '#46403A',
      muted_text_color: '#6C635A',
      border_color: '#E0D8CF',
      border_strong_color: '#8D7F70',
      accent_color: '#835D33',
      accent_text_color: '#FFFFFF',
      secondary_accent_color: '#4C6877',
      success_color: '#2F7856',
      warning_color: '#5F4319',
      danger_color: '#7B2F27',
      info_color: '#3D6DA5',
    };

    async function loadIndustryPresets() {
      try {
        const response = await fetch('/v1/industry-presets', { credentials: 'same-origin' });
        if (!response.ok) throw new Error(`Preset request failed (${response.status})`);
        const data = await response.json();
        if (data.presets && Object.keys(data.presets).length) INDUSTRY_PRESETS = data.presets;
        if (data.styles && Object.keys(data.styles).length) VISUAL_STYLE_PRESETS = data.styles;
      } catch (error) {
        console.warn('Using the generic industry preset.', error);
      }
    }

    let tenant = null;
    let plans = [];
    let currentUser = null;
    let settingsDirty = false;
    let publicationState = 'published'; // 'published' | 'draft' | 'pending' | 'error'
    let lastPublishedPayload = null;
    let lastPublicationError = null;
    let publishedVersionLabel = '';
    let previewMode = 'portal';
    let previewDevice = 'desktop';
    /* Start the visitor preview in the same language as the admin shell. The
       control remains independent after an owner intentionally compares the
       other language. This prevents an English admin from opening on a
       Chinese-looking preview while keeping side-by-side QA possible. */
    let previewLanguage = localStorage.getItem('studiosaas_admin_language') === 'en' ? 'en' : 'zh';
    let previewLanguageManuallySet = false;
    /* Shared by updateThemePreview and renderPreviewSections. It used to be
       declared inside updateThemePreview, which is why the section list — a
       separate function — read only the Chinese label inputs and ignored the
       *LabelEn fields sitting beside them in the form. */
    const localizedValue = (zhId, enId, fallback) =>
      $(previewLanguage === 'zh' ? zhId : enId)?.value || fallback;
    /* Fixed nouns in the preview that have no tenant-editable field. They were
       hardcoded English and stayed English in Chinese mode. */
    const previewNoun = (zh, en) => (previewLanguage === 'zh' ? zh : en);
    let brandVersions = [];
    let activeVisualStyle = '';
    // Light/dark is a separate axis from the palette: a studio picks a
    // theme, then picks how it renders. Both variants are pre-solved.
    let activeColorScheme = 'light';
    /* What the OWNER chose, which is not always what is rendered.
       `system` renders light or dark depending on the visitor's device,
       so the two have to be tracked separately: activeColorScheme drives
       the preview and the swatches, activeSchemePreference is what gets
       saved and what the Appearance control shows. */
    let activeSchemePreference = 'light';
    let themeMode = 'preset';
    let lastPresetSnapshot = null;
    /* About photos live in JS rather than in inputs because the control is a
       list the owner adds to and removes from, and a hidden field holding
       comma-joined URLs would be a second representation to keep in step. */
    let aboutImages = [];
    let aboutImageAlts = [];
    let publishedSurfaceContract = null;
    let draftSurfaceContract = null;
    let previewSource = 'draft';
    let publishedBaselinePayload = null;

    const ABOUT_IMAGE_LIMIT = 6;   // matches _normalize_website_profile
    /* Both mirror api_v1.py. Kept as literals rather than read from /brand so
       a first-time studio, whose record has no timetable block at all, still
       gets the recommended layout instead of every field switched off. */
    const TIMETABLE_DEFAULT_WEEKS = 2;
    const TIMETABLE_FIELD_DEFAULTS = {
      teacher: true, room: true, age_range: true,
      duration: false, capacity: true, price: false,
    };
    const timetableFieldControl = (key) =>
      'settingTimetableField' + key.split('_')
        .map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join('');
    const ABOUT_ITEM_SLOTS = 6;

    /* The studio's own work — see docs/design/Showcase_Section.md.
       State lives here rather than in the DOM because a work is a record with
       five parts, and reading five inputs back out by index is how a reorder
       silently swaps two captions. */
    let showcaseItems = [];
    let showcaseCategories = [];
    // plans.showcase_limit for this tenant. Read from the workspace payload,
    // never assumed — the console must not invent a number that decides what
    // a studio can publish.
    let currentShowcaseLimit = 0;
    // Matches api_v1.SHOWCASE_CATEGORY_LIMIT. There is no item limit here any
    // more: how many are PUBLISHED is the plan's business (plans.showcase_limit)
    // and is decided when the board is read, so the editor shows everything a
    // studio owns regardless of what it currently pays for.
    const SHOWCASE_CATEGORY_LIMIT = 8;
    const SHOWCASE_FEATURED_RANK_MAX = 500;
    const SHOWCASE_PUBLICATION_STATES = ['active', 'draft', 'archived'];

    function normalizeShowcasePublicationState(value) {
      const state = String(value || '').trim().toLowerCase();
      return SHOWCASE_PUBLICATION_STATES.includes(state) ? state : (state ? 'draft' : 'active');
    }

    function normalizeShowcaseFeaturedRank(value) {
      if (value === '' || value === null || value === undefined) return null;
      const rank = Number(value);
      return Number.isInteger(rank) && rank >= 1 && rank <= SHOWCASE_FEATURED_RANK_MAX
        ? rank : null;
    }

    function showcaseHasContent(item) {
      return Boolean(item?.image_url || String(item?.video_url || '').trim());
    }

    function showcaseCountByState() {
      const counts = { active: 0, draft: 0, archived: 0 };
      showcaseItems.forEach((item) => {
        if (!showcaseHasContent(item)) return;
        counts[normalizeShowcasePublicationState(item.publication_state)] += 1;
      });
      return counts;
    }

    function defaultShowcasePublicationState() {
      const limit = Number(currentShowcaseLimit) || 0;
      if (!limit) return 'active';
      const counts = showcaseCountByState();
      return counts.active < limit ? 'active' : 'draft';
    }

    /* ── Uploading ──────────────────────────────────────────────────────
     *
     * Shrink in the browser before sending. This is the single largest
     * improvement available here and it is not about our bandwidth:
     *
     *   - a 24MP phone photo is ~8MB and the per-file limit is 10MB, so a
     *     studio photographing its own work on a phone was one portrait away
     *     from a rejection it could not explain;
     *   - the same photo lands at ~500KB, so a plan's storage holds an order
     *     of magnitude more work;
     *   - and uploading twenty pieces over a phone connection stops being a
     *     coffee break.
     *
     * 2400px is chosen against the layout, not by feel: the lead tile is at
     * most ~1100 CSS px wide, so 2400 covers a 2× display with room spare.
     * Anything larger is asking the visitor to download pixels nobody sees.
     *
     * `imageOrientation: 'from-image'` is load-bearing. Without it every
     * portrait photo taken on a phone arrives lying on its side, because the
     * rotation lives in EXIF and canvas does not apply it. That is the
     * classic way a downscale "works" and ruins the picture.
     */
    const SHOWCASE_MAX_EDGE = 2400;
    const SHOWCASE_JPEG_QUALITY = 0.82;

    async function downscaleImage(file) {
      if (!/^image\/(jpeg|png|webp)$/.test(file.type)) return file;
      let bitmap;
      try {
        bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' });
      } catch {
        return file;   // old browser, or a file the decoder refuses: send as-is
      }
      const longest = Math.max(bitmap.width, bitmap.height);
      const scale = Math.min(1, SHOWCASE_MAX_EDGE / longest);
      const width = Math.round(bitmap.width * scale);
      const height = Math.round(bitmap.height * scale);
      const canvas = document.createElement('canvas');
      canvas.width = width;
      canvas.height = height;
      canvas.getContext('2d').drawImage(bitmap, 0, 0, width, height);
      bitmap.close?.();
      const blob = await new Promise((resolve) =>
        canvas.toBlob(resolve, 'image/jpeg', SHOWCASE_JPEG_QUALITY));
      // Never send something bigger than what we were given. Re-encoding an
      // already-small JPEG, or any PNG screenshot of flat colour, can easily
      // grow it — and then "optimising" would cost the studio quota.
      if (!blob || blob.size >= file.size) return file;
      return new File([blob], file.name.replace(/\.[^.]+$/, '') + '.jpg',
                      { type: 'image/jpeg' });
    }

    /* Same auth shape as `api()`, but XHR — `fetch` cannot report upload
       progress, and a progress bar that is not measured is a lie. */
    function apiUpload(path, formData, onProgress) {
      const slug = currentTenantSlug();
      if (!slug) return Promise.reject(new Error('Tenant slug is required.'));
      return new Promise((resolve, reject) => {
        const request = new XMLHttpRequest();
        request.open('POST', `/s/${encodeURIComponent(slug)}/v1${path}`);
        request.withCredentials = true;
        request.setRequestHeader('X-Requested-With', 'StudioSaaS');
        request.setRequestHeader('X-Tenant-Slug', slug);
        request.upload.addEventListener('progress', (event) => {
          if (event.lengthComputable) onProgress(event.loaded / event.total);
        });
        request.addEventListener('load', () => {
          let data = {};
          try { data = JSON.parse(request.responseText || '{}'); } catch { /* keep {} */ }
          if (request.status >= 200 && request.status < 300) return resolve(data);
          reject(new Error(data.message || data.error || `${request.status} ${path}`));
        });
        request.addEventListener('error', () => reject(new Error('Upload failed.')));
        request.addEventListener('abort', () => reject(new Error('Upload cancelled.')));
        request.send(formData);
      });
    }

    /* One card's picture area, repainted alone.
     *
     * `renderShowcaseItems()` rebuilds the whole list, which is right for a
     * structural change the owner just made (add, remove, reorder) and wrong
     * for an upload finishing — that would destroy the caption they are in
     * the middle of typing three cards down. Uploads patch; people rebuild. */
    function paintShowcaseThumb(host, item, index) {
      host.textContent = '';
      const preview = item._localPreview || item.image_url;
      if (preview) {
        const chip = document.createElement('div');
        chip.className = 'img-chip';
        const img = document.createElement('img');
        img.src = preview;      // property, never interpolated markup
        img.alt = '';
        chip.appendChild(img);
        if (item._uploading) {
          const bar = document.createElement('span');
          bar.className = 'img-chip-progress';
          bar.style.width = `${Math.round((item._progress || 0) * 100)}%`;
          chip.appendChild(bar);
        }
        host.appendChild(chip);
      }
      if (item._error) {
        const failed = document.createElement('p');
        failed.className = 'showcase-upload-error';
        failed.textContent = item._error;
        host.appendChild(failed);
      }
      const file = document.createElement('input');
      file.type = 'file';
      file.accept = 'image/jpeg,image/png,image/webp';
      file.id = `showcaseImage${index}`;
      const fileLabel = document.createElement('label');
      fileLabel.setAttribute('for', file.id);
      fileLabel.textContent = item.image_url ? 'Replace photo' : 'Photo';
      file.addEventListener('change', () => {
        const chosen = file.files[0];
        file.value = '';
        if (chosen) uploadShowcaseImage(item, chosen).catch(reportApiError);
      });
      host.append(fileLabel, file);
    }

    function repaintShowcaseThumb(item) {
      const index = showcaseItems.indexOf(item);
      if (index < 0) return;
      const host = $('showcaseItemsEditor')
        ?.querySelector(`[data-showcase-index="${index}"] .showcase-thumb`);
      if (host) paintShowcaseThumb(host, item, index);
    }

    async function uploadShowcaseImage(item, file) {
      item._uploading = true;
      item._progress = 0;
      item._error = '';
      // Shown from its own bytes straight away: the board takes shape while
      // the network is still working, instead of after it.
      if (item._localPreview) URL.revokeObjectURL(item._localPreview);
      item._localPreview = URL.createObjectURL(file);
      repaintShowcaseThumb(item);
      try {
        const prepared = await downscaleImage(file);
        const formData = new FormData();
        formData.append('target', 'showcase');
        formData.append('file', prepared);
        const data = await apiUpload('/tenant/website-media', formData, (fraction) => {
          item._progress = fraction;
          repaintShowcaseThumb(item);
        });
        item.image_url = data.url || '';
      } catch (error) {
        // One file failing is one card failing. The rest of the batch keeps
        // going, and this card says what happened and can be retried.
        item._error = error.message || 'Upload failed.';
      } finally {
        item._uploading = false;
        if (item._localPreview && item.image_url) {
          URL.revokeObjectURL(item._localPreview);
          item._localPreview = '';
        }
        repaintShowcaseThumb(item);
        renderShowcasePublishNotice();
        setSettingsDirty(true);
      }
      /* Adding work is a request to SHOW the work — the same reasoning as the
         hero photo, and the same dead end avoided. */
      if (item.image_url && !toggleOn('settingShowShowcase')) {
        setToggle('settingShowShowcase', true, true);
      }
    }

    /* Drag a folder of work in, or pick several at once. Cards appear before
       a single byte has been sent, so the wait is visible progress rather
       than an unexplained pause. */
    async function addShowcaseFiles(fileList) {
      const files = [...(fileList || [])]
        .filter((file) => /^image\/(jpeg|png|webp)$/.test(file.type));
      if (!files.length) return;
      let activeSlots = showcaseCountByState().active;
      const limit = Number(currentShowcaseLimit) || 0;
      const queued = files.map((file) => {
        const item = { image_url: '', category_id: '', title: { zh: '', en: '' },
                       caption: { zh: '', en: '' }, video_url: '',
                       featured_rank: null,
                       publication_state: !limit || activeSlots < limit ? 'active' : 'draft',
                       _uploading: true, _progress: 0, _error: '', _localPreview: '' };
        if (item.publication_state === 'active') activeSlots += 1;
        showcaseItems.push(item);
        return { file, item };
      });
      renderShowcaseItems();
      setSettingsDirty(true);
      // Two at a time. Twenty parallel uploads share the same uplink and
      // finish no sooner, but every one of them looks stalled while they do.
      let cursor = 0;
      const worker = async () => {
        while (cursor < queued.length) {
          const next = queued[cursor++];
          await uploadShowcaseImage(next.item, next.file);
        }
      };
      await Promise.all([worker(), worker()]);
      showToast(`${files.length} photo${files.length === 1 ? '' : 's'} added. Save Draft or Publish when ready.`);
    }

    /* What the plan publishes, said plainly and only when it matters.
       A studio that has moved to a smaller plan keeps every work — the editor
       still lists all of them — but the site shows the first N active works.
       Drafts and archived works remain available for later promotion. */
    function renderShowcasePublishNotice() {
      const notice = $('showcasePublishNotice');
      if (!notice) return;
      const limit = Number(currentShowcaseLimit) || 0;
      const counts = showcaseCountByState();
      const visible = limit ? Math.min(counts.active, limit) : counts.active;
      const hidden = Math.max(counts.active - visible, 0);
      const ranked = showcaseItems.filter((item) => normalizeShowcaseFeaturedRank(item.featured_rank) !== null);
      const rankedHidden = limit
        ? ranked.filter((item) => normalizeShowcaseFeaturedRank(item.featured_rank) > limit).length
        : 0;
      const isZh = adminIsZh();
      /* Always-on, quiet: how many of your works the site is showing, and
         that we shrink photos on the way in. Both are things a studio would
         otherwise have to guess at — and the second explains why a 9MB photo
         did not fail. No storage figure: there is no endpoint that reports
         one, and inventing a number here would be worse than saying nothing. */
      const quota = $('showcaseQuota');
      if (quota) {
        quota.textContent = limit
          ? (isZh
            ? `官网公开：${visible}/${limit} 件 active 作品 · 精选排序 ${ranked.length} 件${rankedHidden ? `（${rankedHidden} 件超出当前额度）` : ''} · 草稿 ${counts.draft} · 已归档 ${counts.archived} · 上传前会将照片缩放至 2400px`
            : `Published on your site: ${visible} of ${limit} active works · ${ranked.length} ranked${rankedHidden ? ` (${rankedHidden} beyond this plan's slots)` : ''} · ${counts.draft} draft · ${counts.archived} archived · photos are resized to 2400px before upload`)
          : (isZh
            ? `官网公开 active 作品：${visible} · 精选排序 ${ranked.length} 件 · 草稿 ${counts.draft} · 已归档 ${counts.archived} · 上传前会将照片缩放至 2400px`
            : `Published active works: ${visible} · ${ranked.length} ranked · ${counts.draft} draft · ${counts.archived} archived · photos are resized to 2400px before upload`);
      }
      if (!hidden && !rankedHidden && !counts.draft && !counts.archived) {
        notice.hidden = true;
        return;
      }
      notice.hidden = false;
      notice.textContent = limit
        ? (isZh
          ? `当前套餐最多公开 ${limit} 件 active 作品。精选排序会优先进入公开范围；当前在线 ${visible} 件，另有 ${hidden} 件 active 作品暂不公开。${rankedHidden ? `${rankedHidden} 件已保存精选排序，但超出当前套餐额度。` : ''}作品不会因切换套餐而删除，升级后会按原排序恢复。草稿 ${counts.draft} 件，已归档 ${counts.archived} 件。`
          : `Your plan publishes ${limit} active works. Ranked works take priority; ${visible} are live and ${hidden} active work${hidden === 1 ? '' : 's'} are currently hidden. ${rankedHidden ? `${rankedHidden} ranked work${rankedHidden === 1 ? '' : 's'} sit beyond this plan's slots.` : ''} Nothing is deleted, and an upgrade restores the saved order. Draft: ${counts.draft}; archived: ${counts.archived}.`)
        : (isZh
          ? `作品会按状态保存在这里。active ${visible} 件，草稿 ${counts.draft} 件，已归档 ${counts.archived} 件。切换套餐不会删除作品。`
          : `Works are stored here by status. Active: ${visible}; draft: ${counts.draft}; archived: ${counts.archived}. Nothing is deleted when a plan changes.`);
    }

    function renderShowcaseCategories() {
      const host = $('showcaseCategoryEditor');
      if (!host) return;
      host.textContent = '';
      showcaseCategories.forEach((cat, index) => {
        const row = document.createElement('div');
        row.className = 'form-grid showcase-category-row';
        const field = (suffix, labelText, value, onInput) => {
          const group = document.createElement('div');
          group.className = 'form-group';
          const id = `showcaseCategory${suffix}${index}`;
          const label = document.createElement('label');
          label.setAttribute('for', id);
          label.textContent = labelText;
          const input = document.createElement('input');
          input.id = id;
          input.value = value || '';
          input.addEventListener('input', (e) => { onInput(e.target.value); setSettingsDirty(true); });
          group.append(label, input);
          row.appendChild(group);
        };
        field('', 'Category · 中文', (cat.label || {}).zh,
          (v) => { cat.label = { ...(cat.label || {}), zh: v }; });
        field('En', 'Category · English', (cat.label || {}).en,
          (v) => { cat.label = { ...(cat.label || {}), en: v }; });

        const actions = document.createElement('div');
        actions.className = 'form-group';
        actions.style.gridColumn = '1/-1';
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'btn btn-secondary btn-sm';
        remove.textContent = 'Remove category';
        remove.addEventListener('click', () => {
          // The works keep existing; they lose only their drawer.
          const gone = cat.id;
          showcaseCategories.splice(index, 1);
          showcaseItems.forEach((item) => { if (item.category_id === gone) item.category_id = ''; });
          renderShowcaseCategories();
          renderShowcaseItems();
          setSettingsDirty(true);
        });
        actions.appendChild(remove);
        row.appendChild(actions);
        host.appendChild(row);
      });
      const add = $('showcaseAddCategory');
      if (add) add.disabled = showcaseCategories.length >= SHOWCASE_CATEGORY_LIMIT;
    }

    /* Recognised client-side only to tell the owner immediately whether their
       link worked. The SERVER re-parses every link and is the only thing that
       decides what reaches a page — this is feedback, not validation. */
    function recogniseVideo(url) {
      const text = String(url || '').trim();
      if (!text) return '';
      let host = '';
      try {
        const candidate = /^[a-z][a-z\d+.-]*:\/\//i.test(text) ? text : `https://${text}`;
        host = new URL(candidate).hostname.toLowerCase().replace(/^www\./, '');
      } catch {
        return '?';
      }
      if (['youtube.com', 'm.youtube.com', 'youtube-nocookie.com', 'youtu.be'].includes(host)) return 'YouTube';
      if (['vimeo.com', 'player.vimeo.com'].includes(host)) return 'Vimeo';
      if (['bilibili.com', 'm.bilibili.com', 'player.bilibili.com', 'b23.tv'].includes(host)) return 'Bilibili';
      return '?';
    }

    /* Provider + id back to a link a person recognises. Watch URLs, not embed
       URLs, because this goes in a text box the owner reads and re-copies. */
    function showcaseWatchUrl(provider, videoId) {
      if (!provider || !videoId) return '';
      if (provider === 'youtube') return `https://youtu.be/${videoId}`;
      if (provider === 'vimeo') return `https://vimeo.com/${videoId}`;
      if (provider === 'bilibili') return `https://www.bilibili.com/video/${videoId}`;
      return '';
    }

    function renderShowcaseItems() {
      const host = $('showcaseItemsEditor');
      if (!host) return;
      host.textContent = '';
      showcaseItems.forEach((item, index) => {
        const card = document.createElement('div');
        card.className = 'showcase-card';
        card.dataset.showcaseIndex = String(index);

        const head = document.createElement('div');
        head.className = 'showcase-card-head';
        const badge = document.createElement('span');
        badge.className = 'showcase-rank';
        badge.textContent = item.featured_rank
          ? `Featured #${item.featured_rank}`
          : (index === 0 ? 'Order' : `Fallback ${index + 1}`);
        head.appendChild(badge);
        const spacer = document.createElement('span');
        spacer.style.flex = '1';
        head.appendChild(spacer);
        [['↑', 'Move up', -1], ['↓', 'Move down', 1]].forEach(([glyph, label, delta]) => {
          const move = document.createElement('button');
          move.type = 'button';
          move.className = 'btn btn-secondary btn-sm';
          move.textContent = glyph;
          move.setAttribute('aria-label', `${label}: work ${index + 1}`);
          move.disabled = index + delta < 0 || index + delta >= showcaseItems.length;
          move.addEventListener('click', () => {
            const to = index + delta;
            [showcaseItems[index], showcaseItems[to]] = [showcaseItems[to], showcaseItems[index]];
            renderShowcaseItems();
            setSettingsDirty(true);
          });
          head.appendChild(move);
        });
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'btn btn-secondary btn-sm';
        remove.textContent = 'Remove';
        remove.setAttribute('aria-label', `Remove work ${index + 1}`);
        remove.addEventListener('click', () => {
          showcaseItems.splice(index, 1);
          renderShowcaseItems();
          setSettingsDirty(true);
        });
        head.appendChild(remove);
        card.appendChild(head);

        const body = document.createElement('div');
        body.className = 'form-grid';

        const thumb = document.createElement('div');
        thumb.className = 'form-group showcase-thumb';
        thumb.style.gridColumn = '1/-1';
        paintShowcaseThumb(thumb, item, index);
        body.appendChild(thumb);

        const field = (key, labelText, value, tag, span) => {
          const group = document.createElement('div');
          group.className = 'form-group';
          if (span) group.style.gridColumn = '1/-1';
          const label = document.createElement('label');
          const id = `showcase${key}${index}`;
          label.setAttribute('for', id);
          label.textContent = labelText;
          const input = document.createElement(tag);
          input.id = id;
          if (tag === 'textarea') input.rows = 2;
          input.value = value || '';
          group.append(label, input);
          body.appendChild(group);
          return input;
        };

        field('Title', 'Title · 中文', (item.title || {}).zh, 'input')
          .addEventListener('input', (e) => { item.title = { ...(item.title || {}), zh: e.target.value }; setSettingsDirty(true); });
        field('TitleEn', 'Title · English', (item.title || {}).en, 'input')
          .addEventListener('input', (e) => { item.title = { ...(item.title || {}), en: e.target.value }; setSettingsDirty(true); });
        field('Caption', 'Caption · 中文', (item.caption || {}).zh, 'textarea', true)
          .addEventListener('input', (e) => { item.caption = { ...(item.caption || {}), zh: e.target.value }; setSettingsDirty(true); });
        field('CaptionEn', 'Caption · English', (item.caption || {}).en, 'textarea', true)
          .addEventListener('input', (e) => { item.caption = { ...(item.caption || {}), en: e.target.value }; setSettingsDirty(true); });

        const stateGroup = document.createElement('div');
        stateGroup.className = 'form-group';
        const stateId = `showcasePublicationState${index}`;
        const stateLabel = document.createElement('label');
        stateLabel.setAttribute('for', stateId);
        stateLabel.textContent = 'Publication status';
        const state = document.createElement('select');
        state.id = stateId;
        [
          ['active', 'Active'],
          ['draft', 'Draft'],
          ['archived', 'Archived'],
        ].forEach(([value, label]) => {
          const option = document.createElement('option');
          option.value = value;
          option.textContent = label;
          option.selected = normalizeShowcasePublicationState(item.publication_state) === value;
          state.appendChild(option);
        });
        state.addEventListener('change', () => {
          item.publication_state = normalizeShowcasePublicationState(state.value);
          renderShowcasePublishNotice();
          setSettingsDirty(true);
        });
        stateGroup.append(stateLabel, state);
        body.appendChild(stateGroup);

        const rankGroup = document.createElement('div');
        rankGroup.className = 'form-group';
        const rankId = `showcaseFeaturedRank${index}`;
        const rankLabel = document.createElement('label');
        rankLabel.setAttribute('for', rankId);
        rankLabel.textContent = 'Featured rank (optional)';
        const rank = document.createElement('input');
        rank.id = rankId;
        rank.type = 'number';
        rank.min = '1';
        rank.max = String(SHOWCASE_FEATURED_RANK_MAX);
        rank.step = '1';
        rank.inputMode = 'numeric';
        rank.placeholder = '—';
        rank.value = item.featured_rank ?? '';
        const rankNote = document.createElement('small');
        rankNote.textContent = 'Lower numbers appear first; ranks 1–6 are the home preview.';
        rank.addEventListener('input', () => {
          item.featured_rank = normalizeShowcaseFeaturedRank(rank.value);
          if (rank.value && item.featured_rank === null) rank.setCustomValidity('Use a whole number from 1 to 500.');
          else rank.setCustomValidity('');
          renderShowcasePublishNotice();
          setSettingsDirty(true);
        });
        rankGroup.append(rankLabel, rank, rankNote);
        body.appendChild(rankGroup);

        if (showcaseCategories.length) {
          const catGroup = document.createElement('div');
          catGroup.className = 'form-group';
          const catId = `showcaseItemCategory${index}`;
          const catLabel = document.createElement('label');
          catLabel.setAttribute('for', catId);
          catLabel.textContent = 'Category';
          const select = document.createElement('select');
          select.id = catId;
          [{ id: '', label: { zh: '未分类', en: 'Uncategorised' } }]
            .concat(showcaseCategories).forEach((cat) => {
              const option = document.createElement('option');
              option.value = cat.id;
              option.textContent = (cat.label || {}).en || (cat.label || {}).zh || cat.id;
              if ((item.category_id || '') === cat.id) option.selected = true;
              select.appendChild(option);
            });
          select.addEventListener('change', () => {
            item.category_id = select.value;
            setSettingsDirty(true);
          });
          catGroup.append(catLabel, select);
          body.appendChild(catGroup);
        }

        const videoGroup = document.createElement('div');
        videoGroup.className = 'form-group';
        videoGroup.style.gridColumn = '1/-1';
        const videoLabel = document.createElement('label');
        const videoId = `showcaseVideo${index}`;
        videoLabel.setAttribute('for', videoId);
        videoLabel.textContent = 'Video link (optional)';
        const video = document.createElement('input');
        video.id = videoId;
        video.placeholder = 'https://youtu.be/… · https://vimeo.com/… · https://www.bilibili.com/video/BV…';
        video.value = item.video_url || '';
        const note = document.createElement('small');
        /* Told immediately, not at Save. A studio that pastes a channel URL
           instead of a video URL should find out while the link is still on
           their clipboard. */
        const describe = () => {
          const seen = recogniseVideo(video.value);
          const isZh = adminIsZh();
          const provider = isZh && seen === 'Bilibili' ? '哔哩哔哩' : seen;
          note.textContent = !seen
            ? (isZh ? '未填写视频链接，前台只展示照片。' : 'The photo is shown on its own.')
            : seen === '?'
              ? (isZh ? '无法识别该链接——仅支持 YouTube、Vimeo 和哔哩哔哩。'
                : 'Not a recognised link — only YouTube, Vimeo and Bilibili can be embedded.')
              : (isZh ? `已识别：${provider}。上方照片会作为封面；访客点击播放后才加载视频。`
                : `Recognised: ${provider}. The photo above becomes the cover; the video loads only when a visitor presses play.`);
        };
        video.addEventListener('input', () => {
          item.video_url = video.value;
          describe();
          setSettingsDirty(true);
        });
        describe();
        videoGroup.append(videoLabel, video, note);
        body.appendChild(videoGroup);

        card.appendChild(body);
        host.appendChild(card);
      });
      renderShowcasePublishNotice();
    }


    function collectShowcaseItems() {
      return showcaseItems
        .filter((item) => item.image_url || String(item.video_url || '').trim())
        .map((item) => ({
          imageUrl: item.image_url || '',
          categoryId: item.category_id || '',
          featuredRank: normalizeShowcaseFeaturedRank(item.featured_rank),
          publicationState: normalizeShowcasePublicationState(item.publication_state),
          // One filled language serves both, same rule as the FAQ and About.
          title: { zh: (item.title || {}).zh || (item.title || {}).en || '',
                   en: (item.title || {}).en || (item.title || {}).zh || '' },
          caption: { zh: (item.caption || {}).zh || (item.caption || {}).en || '',
                     en: (item.caption || {}).en || (item.caption || {}).zh || '' },
          // The raw link goes up; the SERVER parses it. Sending a
          // client-parsed provider/id would put a second parser in the trust
          // path, and the browser's copy is the one an attacker controls.
          videoUrl: String(item.video_url || '').trim()
        }));
    }

    /* A {zh, en} pair for the server's `_localized_pair`.
       NOT `localizedValue`, which reads whichever field matches the PREVIEW
       language and returns one string — right for drawing the preview, and it
       would silently save half the copy. */
    const bilingualPair = (zhId, enId) => ({
      zh: ($(zhId)?.value || '').trim(),
      en: ($(enId)?.value || '').trim()
    });

    function renderAboutItems(items) {
      const host = $('settingAboutItems');
      if (!host) return;
      const source = Array.isArray(items) ? items : [];
      host.textContent = '';
      for (let i = 0; i < ABOUT_ITEM_SLOTS; i += 1) {
        const item = source[i] || {};
        const title = item.title || {};
        const body = item.body || {};
        // Built with DOM calls rather than an innerHTML template because every
        // one of these values is tenant-authored text.
        [
          [`aboutItemTitle${i}`, `Highlight ${i + 1} Title · 中文`, title.zh, 'input'],
          [`aboutItemTitleEn${i}`, `Highlight ${i + 1} Title · English`, title.en, 'input'],
          [`aboutItemBody${i}`, `Highlight ${i + 1} Body · 中文`, body.zh, 'textarea'],
          [`aboutItemBodyEn${i}`, `Highlight ${i + 1} Body · English`, body.en, 'textarea']
        ].forEach(([id, labelText, value, tag]) => {
          const group = document.createElement('div');
          group.className = 'form-group';
          if (tag === 'textarea') group.style.gridColumn = '1/-1';
          const label = document.createElement('label');
          label.setAttribute('for', id);
          label.textContent = labelText;
          const field = document.createElement(tag);
          field.id = id;
          if (tag === 'textarea') field.rows = 2;
          field.value = value || '';
          field.addEventListener('input', () => {
            setSettingsDirty(true);
            renderAboutReadiness();
            updateThemePreview();
          });
          group.append(label, field);
          host.appendChild(group);
        });
      }
    }

    function collectAboutItems() {
      const items = [];
      for (let i = 0; i < ABOUT_ITEM_SLOTS; i += 1) {
        const read = (id) => ($(id)?.value || '').trim();
        const titleZh = read(`aboutItemTitle${i}`);
        const titleEn = read(`aboutItemTitleEn${i}`);
        const bodyZh = read(`aboutItemBody${i}`);
        const bodyEn = read(`aboutItemBodyEn${i}`);
        // Same rule as collectFaqItems: one filled language serves both, so a
        // studio writing only Chinese does not publish an empty English card.
        if (!titleZh && !titleEn) continue;
        items.push({
          title: { zh: titleZh || titleEn, en: titleEn || titleZh },
          body: { zh: bodyZh || bodyEn, en: bodyEn || bodyZh }
        });
      }
      return items;
    }

    function renderAboutImages() {
      const host = $('settingAboutImages');
      if (!host) return;
      host.textContent = '';
      aboutImages.forEach((url, index) => {
        const chip = document.createElement('div');
        chip.className = 'about-media-card';
        const img = document.createElement('img');
        // Assigned as a property, never interpolated into markup: these URLs
        // come back from the media endpoint but are stored tenant data.
        img.src = url;
        img.alt = (aboutImageAlts[index]?.[previewLanguage] || '').trim();
        const lead = document.createElement('strong');
        lead.textContent = index === 0 ? adminText('首图', 'Lead') : `${index + 1}`;
        const controls = document.createElement('div');
        controls.className = 'about-media-controls';
        const moveButton = (label, delta, ariaLabel) => {
          const button = document.createElement('button');
          button.type = 'button';
          button.className = 'btn-secondary btn-sm';
          button.textContent = label;
          button.setAttribute('aria-label', ariaLabel);
          button.disabled = index + delta < 0 || index + delta >= aboutImages.length;
          button.addEventListener('click', () => {
            const target = index + delta;
            [aboutImages[index], aboutImages[target]] = [aboutImages[target], aboutImages[index]];
            [aboutImageAlts[index], aboutImageAlts[target]] = [aboutImageAlts[target], aboutImageAlts[index]];
            renderAboutImages();
            setSettingsDirty(true);
            updateThemePreview();
          });
          return button;
        };
        controls.append(
          moveButton('←', -1, `Move About photo ${index + 1} earlier`),
          moveButton('→', 1, `Move About photo ${index + 1} later`),
        );
        const altZh = document.createElement('input');
        altZh.placeholder = '图片说明 · 中文';
        altZh.value = aboutImageAlts[index]?.zh || '';
        altZh.setAttribute('aria-label', `About photo ${index + 1} description in Chinese`);
        const altEn = document.createElement('input');
        altEn.placeholder = 'Image description · English';
        altEn.value = aboutImageAlts[index]?.en || '';
        altEn.setAttribute('aria-label', `About photo ${index + 1} description in English`);
        altZh.addEventListener('input', () => {
          aboutImageAlts[index] = { ...(aboutImageAlts[index] || {}), zh: altZh.value };
          setSettingsDirty(true); updateThemePreview();
        });
        altEn.addEventListener('input', () => {
          aboutImageAlts[index] = { ...(aboutImageAlts[index] || {}), en: altEn.value };
          setSettingsDirty(true); updateThemePreview();
        });
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.textContent = '×';
        remove.setAttribute('aria-label', `Remove About photo ${index + 1}`);
        remove.addEventListener('click', () => {
          aboutImages.splice(index, 1);
          aboutImageAlts.splice(index, 1);
          renderAboutImages();
          setSettingsDirty(true);
          updateThemePreview();
        });
        chip.append(img, lead, controls, altZh, altEn, remove);
        host.appendChild(chip);
      });
      const picker = $('settingAboutImageFile');
      if (picker) picker.disabled = aboutImages.length >= ABOUT_IMAGE_LIMIT;
      renderAboutReadiness();
    }

    function renderAboutReadiness() {
      const note = $('aboutReadinessNote');
      if (!note) return;
      const copyReady = Boolean([
        'settingAboutTitle', 'settingAboutTitleEn', 'settingAboutBody', 'settingAboutBodyEn',
      ].some((id) => ($(id)?.value || '').trim()));
      const ready = copyReady || aboutImages.length > 0 || collectAboutItems().length > 0;
      note.dataset.ready = String(ready);
      note.textContent = ready
        ? adminText('内容已就绪；发布后显示在欢迎信息之后、主理人之前。', 'Content ready; after publishing it appears after the welcome and before the principal.')
        : adminText('请添加标题、介绍、照片或亮点，模块才会公开显示。', 'Add a title, description, photo, or highlight before this module can appear publicly.');
    }

    /* One readout, not two. Until v8.3.0 the same fact was published to the
       save bar ("No unsaved changes") and to a hero badge ("Saved") in two
       different wordings, which meant two places to keep in step and two
       chances for them to disagree. The hero is gone; the bar is the state. */
    function localiseAdminText(value) {
      return window.AdminI18n?.translate?.(value) || value;
    }

    function updateWorkspaceStatus() {
      const status = $('saveBarStatus');
      const previewState = $('previewStateLabel');
      const publicationLabel = $('publicationStateLabel');
      const publicationHelp = $('publicationStateHelp');
      const dirtyText = publicationState === 'error'
        ? 'Publish failed — changes are not confirmed public'
        : publicationState === 'draft'
          ? 'Unsaved changes — saved draft is not public'
          : 'Unsaved changes';
      const cleanText = publicationState === 'error'
        ? 'Publish needs attention'
        : publicationState === 'pending'
          ? 'Published, public pages still need verification'
        : publicationState === 'draft'
          ? 'Draft saved — not public'
          : (publishedVersionLabel ? `Published version ${publishedVersionLabel}` : 'No unsaved changes');
      if (status) {
        status.textContent = localiseAdminText(settingsDirty ? dirtyText : cleanText);
        status.dataset.tone = settingsDirty ? 'dirty' : 'clean';
      }
      if (previewState) {
        previewState.textContent = localiseAdminText(publicationState === 'error'
          ? 'Draft preview — publish needs attention'
          : publicationState === 'pending'
            ? 'Published, public pages still need verification'
          : publicationState === 'draft'
            ? 'Draft preview — not public until Publish'
            : 'Draft preview — compare with the published website before publishing');
      }
      if (publicationLabel) {
        publicationLabel.textContent = localiseAdminText(settingsDirty
          ? publicationState === 'error'
            ? 'Publish needs attention'
            : 'Changes waiting to be saved'
          : publicationState === 'pending'
              ? 'Published, public pages still need verification'
              : publicationState === 'draft'
              ? 'Draft saved — not public'
              : publicationState === 'error'
                ? 'Publish needs attention'
                : (publishedVersionLabel ? `Published version ${publishedVersionLabel}` : 'Published content'));
      }
      if (publicationHelp) {
        publicationHelp.textContent = localiseAdminText(publicationState === 'error'
          ? 'Check the error, save the draft if needed, then publish again.'
          : publicationState === 'pending'
            ? 'The write succeeded. Recheck the public pages; your saved content is safe while verification catches up.'
          : settingsDirty
            ? 'Save a draft to keep the work private, or publish after checking the preview.'
            : publicationState === 'draft'
              ? 'The current editor values are a private draft. Publish when the public pages are ready.'
              : 'The current editor values match the published tenant pages.');
      }
    }

    function setPublicationState(state, versionLabel = '') {
      publicationState = ['draft', 'error'].includes(state) || state === 'pending' ? state : 'published';
      publishedVersionLabel = versionLabel || '';
      const retry = $('retryPublishVerificationBtn');
      if (retry) retry.hidden = publicationState !== 'pending';
      updateWorkspaceStatus();
    }

    function setSettingsDirty(isDirty = true) {
      settingsDirty = isDirty;
      updateWorkspaceStatus();
      renderPublishChanges();
    }

    function renderPublishChanges() {
      const box = $('publishChangeList');
      if (!box || !publishedBaselinePayload || !tenant) return;
      const current = settingsPayload();
      const groups = [
        ['Brand foundation', ['name', 'logoUrl', 'primaryColor', 'secondaryColor', 'contactPhone', 'contactEmail', 'address', 'visualTheme']],
        ['Hero & actions', ['localizedCopy', 'heroProfile']],
        ['Website modules', ['websiteProfile']],
        ['Principal', ['principalProfile']],
        ['Registration', ['registrationProfile', 'copyPack']],
        ['FAQ & messages', ['faqItems', 'messageTemplates']],
      ];
      const changed = groups.filter(([, keys]) => keys.some((key) =>
        JSON.stringify(current[key] ?? null) !== JSON.stringify(publishedBaselinePayload[key] ?? null)));
      box.replaceChildren();
      if (!changed.length) {
        box.textContent = adminText('没有未发布的改动。', 'No unpublished changes.');
        return;
      }
      changed.forEach(([label]) => {
        const row = document.createElement('div'); row.textContent = `• ${localiseAdminText(label)}`; box.appendChild(row);
      });
    }

    function showToast(message, type = 'success') {
      const toast = document.createElement('div');
      toast.className = `toast ${type}`;
      toast.textContent = message;
      $('toastContainer').appendChild(toast);
      setTimeout(() => toast.remove(), 4200);
    }

    function tenantSurfaceUrl(surface) {
      const slug = encodeURIComponent(currentTenantSlug());
      if (!slug) return '#';
      const routes = {
        portal: `/${slug}`,
        cms: `/${slug}/cms`,
        register: `/${slug}/register`,
        admin: `/${slug}/studio-admin`,
        'studio-admin': `/${slug}/studio-admin`
      };
      return routes[surface] || routes.portal;
    }

    function openTenantSurface(surface) {
      const url = tenantSurfaceUrl(surface);
      if (url === '#') {
        showToast(adminText('请先填写工作室网址标识。', 'Tenant slug is required.'), 'error');
        return;
      }
      window.open(url, '_blank');
    }

    function updateSurfaceLinks() {
      const slug = currentTenantSlug();
      const label = $('tenantSlugLabel');
      if (label) label.textContent = slug || 'tenant';
      const urlTargets = {
        surfacePortalUrl: 'portal',
        surfaceCmsUrl: 'cms',
        surfaceRegisterUrl: 'register',
        surfaceAdminUrl: 'admin',
        surfacePortalUrlPreview: 'portal',
        surfaceCmsUrlPreview: 'cms',
        surfaceRegisterUrlPreview: 'register',
        surfaceAdminUrlPreview: 'admin'
      };
      Object.entries(urlTargets).forEach(([id, surface]) => {
        const el = $(id);
        if (el) el.textContent = tenantSurfaceUrl(surface);
      });
      const cmsLink = $('openCmsLink');
      if (cmsLink) {
        if (slug) {
          cmsLink.href = tenantSurfaceUrl('cms');
          cmsLink.style.display = '';
        } else {
          cmsLink.style.display = 'none';
        }
      }
    }

    function setSurfaceHealth(id, state, label) {
      const el = document.getElementById(id);
      if (!el) return;
      el.className = `surface-health ${state || ''}`.trim();
      el.textContent = label;
    }

    async function updateProducerCredit() {
      try {
        const healthResponse = await fetch('/v1/health', { cache: 'no-store' });
        if (!healthResponse.ok) throw new Error(`Health ${healthResponse.status}`);
        const health = await healthResponse.json();
        $('studioProducerCredit').hidden = !health.showProducerCredit;
      } catch (error) {
        $('studioProducerCredit').hidden = true;
        console.warn('Producer credit policy unavailable.', error);
      }
    }

    async function updateSurfaceHealth() {
      await updateProducerCredit();
      const slug = currentTenantSlug();
      const checks = [
        ['surfacePortalHealth', 'portal', '官网', 'Portal'],
        ['surfaceCmsHealth', 'cms', '运营 CMS', 'CMS'],
        ['surfaceRegisterHealth', 'register', '报名', 'Register'],
        ['surfaceAdminHealth', 'admin', '工作室管理', 'Studio Admin']
      ];
      if (!slug) {
        checks.forEach(([id]) => setSurfaceHealth(id, 'warn', adminText('缺少网址标识', 'Missing slug')));
        return;
      }
      checks.forEach(([id]) => setSurfaceHealth(id, 'warn', adminText('检查中…', 'Checking...')));
      await Promise.all(checks.map(async ([id, surface, labelZh, labelEn]) => {
        const label = adminText(labelZh, labelEn);
        try {
          const response = await fetch(tenantSurfaceUrl(surface), { credentials: 'same-origin', cache: 'no-store' });
          if (response.ok) {
            setSurfaceHealth(id, 'ok', `${label} ${adminText('正常', 'OK')}`);
          } else if ([401, 403].includes(response.status)) {
            setSurfaceHealth(id, 'warn', `${label} ${adminText('需要登录', 'requires login')}`);
          } else {
            setSurfaceHealth(id, 'fail', `${label} ${response.status}`);
          }
        } catch (err) {
          setSurfaceHealth(id, 'fail', `${label} ${adminText('不可用', 'unavailable')}`);
        }
      }));
    }

    async function runUiAction(buttonId, label, action) {
      const button = $(buttonId);
      const previous = button ? button.textContent : '';
      if (button) {
        button.disabled = true;
        button.classList.add('btn-loading');
        button.textContent = label;
      }
      try {
        await action();
      } catch (err) {
        // Save Draft and Publish hit the same support gate as the uploads.
        reportApiError(err);
        return false;
      } finally {
        if (button) {
          button.disabled = false;
          button.classList.remove('btn-loading');
          button.textContent = previous;
        }
      }
      return true;
    }

    async function authApi(path, options = {}) {
      const headers = { 'X-Requested-With': 'StudioSaaS', ...(options.headers || {}) };
      if (!(options.body instanceof FormData)) headers['Content-Type'] = 'application/json';
      const res = await fetch(`/v1${path}`, { ...options, credentials: 'include', headers });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const err = new Error(data.message || data.error || `${res.status} ${path}`);
        err.status = res.status;
        throw err;
      }
      return data;
    }

    async function api(path, options = {}) {
      const slug = currentTenantSlug();
      if (!slug) throw new Error('Tenant slug is required.');
      const headers = { 'X-Requested-With': 'StudioSaaS', ...(options.headers || {}), 'X-Tenant-Slug': slug };
      if (!(options.body instanceof FormData)) headers['Content-Type'] = 'application/json';
      const base = path === '/plans' ? '/v1' : `/s/${encodeURIComponent(slug)}/v1`;
      const res = await fetch(base + path, { ...options, credentials: 'include', headers });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const err = new Error(data.message || data.error || `${res.status} ${path}`);
        err.status = res.status;
        /* A platform operator acting on a tenant must open a support session
           first. The server says so clearly, but Studio Admin gave no route to
           it, so the message read as a dead end. Flagged here so the caller can
           offer the console link. */
        err.needsSupportSession = data.error === 'support_session_required';
        throw err;
      }
      return data;
    }

    /* Surfaces an API failure, and for the support-session gate adds the one
       action that resolves it. Super-admin work on a tenant is already written
       to audit_logs with the session marker merged in, so this only exposes a
       route that existed. */
    function reportApiError(err) {
      if (err && err.needsSupportSession) {
        showToast(err.message, 'error');
        const link = document.createElement('a');
        link.href = '/platform-admin#tenants';
        link.target = '_blank';
        link.rel = 'noopener';
        link.className = 'toast error support-gate-toast';
        link.textContent = adminText(
          '前往平台控制台开启支持会话 →',
          'Open a support session in the platform console →',
        );
        $('toastContainer').appendChild(link);
        setTimeout(() => link.remove(), 9000);
        return;
      }
      showToast((err && err.message) || 'Action failed.', 'error');
    }

    /* The i18n dictionary translates text nodes after render; strings built in
       JS need the current language at build time. */
    function adminText(zh, en) {
      return (document.documentElement.lang || '').toLowerCase().startsWith('en') ? en : zh;
    }

    function currentMembershipForSlug(memberships = [], slug) {
      // Platform authority is a super_admin membership with NO tenant; a
      // legacy tenant-scoped super_admin row must not unlock other tenants
      // (mirrors _has_platform_super_admin_membership on the backend).
      return memberships.some((m) =>
        (m.role === 'super_admin' && !m.tenant_slug && !m.slug)
        || ((m.role === 'owner' || m.role === 'super_admin') && (m.tenant_slug === slug || m.slug === slug)));
    }

    function setAuthState(user) {
      currentUser = user;
      const signedIn = Boolean(user);
      $('loginPanel').classList.toggle('hidden', signedIn);
      /* While the load-blocked panel is up the editor stays hidden even for
         a signed-in user; only a successful refresh() lifts it. */
      $('adminContent').classList.toggle('hidden', !signedIn || loadBlocked);
      if (!signedIn) {
        loadBlocked = false;
        $('loadErrorPanel').classList.add('hidden');
      }
      $('changePasswordBtn').classList.toggle('hidden', !signedIn);
      $('logoutBtn').classList.toggle('hidden', !signedIn);
      $('studioNav').classList.toggle('hidden', !signedIn);
      document.querySelectorAll('.requires-auth').forEach((element) => element.classList.toggle('hidden', !signedIn));
      $('authStatus').textContent = signedIn ? `Signed in as ${user.email || user.name || 'admin'}` : 'Not signed in';
      /* Signing in reveals the nav and the refresh button, which is the one
         moment the header changes height by a lot. The ResizeObserver would
         also catch it, but only on the next rendered frame — and a background
         tab does not render. Measured here so the offset is right the first
         time the console is painted. */
      syncHeaderOffset();
    }

    async function checkSession() {
      const knownSlug = currentTenantSlug();
      if (!knownSlug) {
        setAuthState(null);
        setLoginError('No studio selected. Open this console from your studio URL: /<your-studio-slug>/studio-admin.');
        return;
      }
      try {
        const data = await authApi('/auth/me');
        const slug = currentTenantSlug();
        if (data.memberships && !currentMembershipForSlug(data.memberships, slug)) {
          setAuthState(null);
          showToast(`Studio Admin requires the owner role for ${slug}. Open Studio CMS for operational access.`, 'error');
          return;
        }
        setAuthState(data.user || data);
        renderSupportBanner(data.support);
        await refresh();
      } catch (err) {
        setAuthState(null);
        if (err.status && err.status !== 401) showToast(`Session check failed: ${err.message}`, 'error');
      }
    }

    function renderSupportBanner(support) {
      const existing = document.getElementById('supportBanner');
      if (existing) existing.remove();
      if (!support || support.slug !== currentTenantSlug()) return;
      const banner = document.createElement('div');
      banner.id = 'supportBanner';
      banner.style.cssText = 'position:sticky;top:0;z-index:2000;background:var(--on-warning-soft);color:var(--panel);padding:10px 16px;display:flex;align-items:center;gap:12px;font-size:14px;';
      const label = document.createElement('strong');
      // SVG-only (v7.3.2 icon rule): the lifebuoy emoji renders per-platform.
      // Decorative — the SUPPORT MODE text carries the meaning.
      label.style.cssText = 'display:inline-flex;align-items:center;gap:6px;';
      label.innerHTML = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true" focusable="false" style="width:15px;height:15px;flex:0 0 auto;"><circle cx="8" cy="8" r="6.25"/><circle cx="8" cy="8" r="2.75"/><path d="M3.6 3.6l2.45 2.45M9.95 9.95l2.45 2.45M12.4 3.6L9.95 6.05M6.05 9.95L3.6 12.4"/></svg>SUPPORT MODE';
      const detail = document.createElement('span');
      detail.style.flex = '1';
      detail.textContent = `Acting inside ${support.tenant_name || support.slug} — every action is audited. Reason: ${support.reason || ''}`;
      const exitBtn = document.createElement('button');
      exitBtn.type = 'button';
      exitBtn.className = 'btn-secondary btn-sm';
      exitBtn.textContent = 'Exit Support Mode';
      exitBtn.addEventListener('click', async () => {
        try {
          await fetch('/v1/admin/support-session/end', { method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' } });
        } catch (err) { /* best effort */ }
        banner.remove();
        showToast('Support mode ended.');
        location.href = '/platform-admin';
      });
      banner.appendChild(label);
      banner.appendChild(detail);
      banner.appendChild(exitBtn);
      document.body.prepend(banner);
    }

    // Inline login errors mirror the toast so the failure stays visible in the
    // form (role="alert"), with the offending field marked and focused —
    // same pattern as tenant-template/register.html failFirst().
    function setLoginError(message, focusTarget) {
      const box = $('loginError');
      box.textContent = message;
      box.hidden = false;
      if (focusTarget) {
        focusTarget.setAttribute('aria-invalid', 'true');
        focusTarget.focus();
      }
    }

    function clearLoginError() {
      const box = $('loginError');
      box.textContent = '';
      box.hidden = true;
      ['loginEmail', 'loginPassword'].forEach((id) => $(id).removeAttribute('aria-invalid'));
    }

    /* Brand form inline errors (v7.5.0 login pattern, per field): the toast
       still fires via the thrown Error, but the failure also stays visible
       under the offending input, marked with aria-invalid and announced
       through the aria-describedby span. Cleared as soon as the field edits. */
    const BRAND_ERROR_FIELDS = [
      'settingName', 'settingEmail', 'settingPhone', 'settingLogoUrl', 'settingTimezone',
      'settingPrimaryColor', 'settingSecondaryColor',
      'settingThemeBackground', 'settingThemePanel', 'settingThemeText', 'settingThemeMuted', 'settingThemeBorder'
    ];

    function setFieldError(id, message) {
      const input = $(id);
      const box = $(`${id}Error`);
      if (!input || !box) return;
      box.textContent = message;
      box.hidden = false;
      input.setAttribute('aria-invalid', 'true');
    }

    function clearFieldError(id) {
      const input = $(id);
      const box = $(`${id}Error`);
      if (input) input.removeAttribute('aria-invalid');
      if (box) {
        box.textContent = '';
        box.hidden = true;
      }
    }

    function clearBrandFieldErrors() {
      BRAND_ERROR_FIELDS.forEach(clearFieldError);
    }

    const isValidEmail = (value) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
    const isValidPhone = (value) => /^\+?[0-9][0-9\s().-]{4,18}$/.test(value);
    const isValidHexColour = (value) => /^#[0-9a-fA-F]{6}$/.test(value);
    const isValidLogoUrl = (value) => {
      if (/^\/[^\s]*$/.test(value)) return true;
      try {
        return ['http:', 'https:'].includes(new URL(value).protocol);
      } catch (err) {
        return false;
      }
    };
    const isValidTimezone = (value) => {
      try {
        new Intl.DateTimeFormat('en-AU', { timeZone: value });
        return true;
      } catch (err) {
        return false;
      }
    };

    // Returns the list of [fieldId, message] problems; empty when the form is
    // consistent. Colour inputs are type=color so a bad hex normally cannot
    // happen through the UI, but drafts and presets are still checked.
    function collectBrandFieldErrors() {
      const errors = [];
      if (!$('settingName').value.trim()) errors.push(['settingName', 'Studio name is required.']);
      const email = $('settingEmail').value.trim();
      if (email && !isValidEmail(email)) errors.push(['settingEmail', 'Enter a valid email address, like studio@example.com.']);
      const phone = $('settingPhone').value.trim();
      if (phone && !isValidPhone(phone)) errors.push(['settingPhone', 'Enter a valid phone number.']);
      const logoUrl = $('settingLogoUrl').value.trim();
      if (logoUrl && !isValidLogoUrl(logoUrl)) errors.push(['settingLogoUrl', 'Enter a valid logo URL: a tenant asset path or a full https:// address.']);
      const timezone = $('settingTimezone').value.trim();
      if (timezone && !isValidTimezone(timezone)) errors.push(['settingTimezone', 'Unknown timezone. Use an IANA name like Australia/Melbourne.']);
      [
        'settingPrimaryColor', 'settingSecondaryColor',
        'settingThemeBackground', 'settingThemePanel', 'settingThemeText', 'settingThemeMuted', 'settingThemeBorder'
      ].forEach((id) => {
        if (!isValidHexColour($(id).value.trim())) errors.push([id, 'Enter a colour in #RRGGBB format.']);
      });
      return errors;
    }

    // Shows every problem inline, moves to the Brand tab, focuses the first
    // offending field, and throws so the caller's toast contract still holds.
    function validateBrandFields() {
      clearBrandFieldErrors();
      const errors = collectBrandFieldErrors();
      if (!errors.length) return;
      errors.forEach(([id, message]) => setFieldError(id, message));
      switchWorkbenchTab('brand');
      const [firstId, firstMessage] = errors[0];
      const input = $(firstId);
      if (input) {
        const details = input.closest('details');
        if (details) details.open = true; // theme colours live in "Fine-tune"
        if (typeof input.scrollIntoView === 'function') input.scrollIntoView({ block: 'center' });
        input.focus();
      }
      throw new Error(firstMessage);
    }

    async function loginStudioAdmin(event) {
      event.preventDefault();
      clearLoginError();
      const email = $('loginEmail').value.trim();
      const password = $('loginPassword').value;
      if (!email || !password) {
        showToast('Email and password are required.', 'error');
        setLoginError('Email and password are required.', !email ? $('loginEmail') : $('loginPassword'));
        return;
      }
      /* Not runUiAction: that helper CATCHES internally (toast + return
       * false), so a .catch chained on it never fires — which left a failed
       * login with a 3-second toast and no persistent error. The login box
       * (role=alert) is the durable, accessible feedback; render it here,
       * the way Super Admin's login always has. */
      const btn = $('loginBtn');
      btn.disabled = true;
      const originalLabel = btn.textContent;
      btn.textContent = 'Logging in…';
      try {
        await authApi('/auth/login', { method: 'POST', body: JSON.stringify({ email, password, rememberMe: $('loginRemember').checked }) });
        $('loginPassword').value = '';
        showToast('Logged in.');
        await checkSession();
      } catch (err) {
        const message = err.status === 429
          ? 'Too many login attempts — please wait a minute and try again.'
          : err.status === 401 ? 'Invalid email or password.' : (err.message || 'Login failed.');
        showToast(message, 'error');
        setLoginError(message, err.status === 401 ? $('loginPassword') : null);
      } finally {
        btn.disabled = false;
        btn.textContent = originalLabel;
      }
    }

    (function wireLoginPwToggle() {
      const input = $('loginPassword');
      const toggle = $('loginPwToggle');
      if (!input || !toggle) return;
      toggle.addEventListener('click', () => {
        const showing = input.type === 'text';
        input.type = showing ? 'password' : 'text';
        toggle.textContent = showing ? 'Show' : 'Hide';
      });
    })();

    async function logoutStudioAdmin() {
      try {
        await authApi('/auth/logout', { method: 'POST' });
      } catch (err) {
        showToast(`Logout failed: ${err.message}`, 'error');
        return;
      }
      setAuthState(null);
      showToast('Logged out.');
    }

    function openChangePasswordModal() {
      const bodyHtml = `
        <div class="form-group"><label for="m_oldPassword">Current Password</label><input id="m_oldPassword" type="password" autocomplete="current-password"></div>
        <div class="form-group"><label for="m_newPassword">New Password</label><input id="m_newPassword" type="password" autocomplete="new-password" placeholder="At least 8 characters"></div>
        <div class="form-group"><label for="m_confirmPassword">Confirm New Password</label><input id="m_confirmPassword" type="password" autocomplete="new-password"></div>
      `;
      const footerHtml = `<button onclick="changePassword()" class="btn-primary">Update Password</button><button onclick="closeModal()" class="btn-secondary">Cancel</button>`;
      openModal('Change Password', bodyHtml, footerHtml);
    }

    async function changePassword() {
      const oldPassword = $('m_oldPassword').value;
      const newPassword = $('m_newPassword').value;
      const confirmPassword = $('m_confirmPassword').value;
      if (newPassword !== confirmPassword) {
        showToast('New passwords do not match.', 'error');
        return;
      }
      /* H3: a failed change used to reject silently — the modal stayed open
         with no feedback, so a wrong current password looked like success.
         Same catch+toast contract as super-admin.html changePassword(). */
      try {
        await authApi('/auth/change-password', { method: 'POST', body: JSON.stringify({ oldPassword, newPassword }) });
        closeModal();
        showToast('Password updated.');
      } catch (err) {
        showToast(err.status === 401 ? 'Current password is incorrect.' : err.message, 'error');
      }
    }

    let modalReturnFocus = null;

    function openModal(title, bodyHtml, footerHtml) {
      modalReturnFocus = document.activeElement;
      $('modalTitle').textContent = title;
      $('modalBody').innerHTML = bodyHtml;
      $('modalFooter').innerHTML = footerHtml;
      $('modalOverlay').classList.add('active');
      const focusTarget = $('modalBody').querySelector('input, select, textarea, button') || $('modalFooter').querySelector('button');
      if (focusTarget) focusTarget.focus();
    }

    function closeModal() {
      $('modalOverlay').classList.remove('active');
      if (modalReturnFocus && typeof modalReturnFocus.focus === 'function') modalReturnFocus.focus();
      modalReturnFocus = null;
    }

    // Keep Tab and Shift+Tab cycling inside the open dialog.
    function trapModalFocus(event) {
      if (event.key !== 'Tab') return;
      const focusable = Array.from($('modalOverlay').querySelectorAll('button, [href], input, select, textarea'))
        .filter((element) => !element.disabled && element.offsetParent !== null);
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    function categoryOptions(selected) {
      return Object.entries(INDUSTRY_PRESETS).map(([key, preset]) => `<option value="${esc(key)}" ${key === selected ? 'selected' : ''}>${esc(preset.label)}</option>`).join('');
    }

    /* settingsPayload() sends localizedCopy in camelCase and the brand-workspace
       draft stores it verbatim, while every reader here uses snake_case. Without
       this, loading a saved draft dropped multi-word keys (hero_title, and now
       the class-B identity pairs) back to their industry defaults. */
    const snakeLocalizedCopy = (source) => {
      const out = {};
      Object.entries(source && typeof source === 'object' ? source : {}).forEach(([key, pair]) => {
        out[key.replace(/([A-Z])/g, (match) => `_${match.toLowerCase()}`)] = pair;
      });
      return out;
    };

    const industryPresetFor = (category) =>
      INDUSTRY_PRESETS[category || $('settingCategory')?.value || 'general'] || INDUSTRY_PRESETS.general;

    function defaultRegistrationProfile(category) {
      const preset = INDUSTRY_PRESETS[category] || INDUSTRY_PRESETS.general;
      return JSON.parse(JSON.stringify(preset.registrationProfile || INDUSTRY_PRESETS.general.registrationProfile));
    }

    function boolValue(value, fallback = true) {
      if (value === undefined || value === null || value === '') return fallback;
      if (typeof value === 'string') return value !== 'false';
      return Boolean(value);
    }

    /* The visibility settings are switches, so their state is .checked rather
       than the string 'true'/'false' a two-option <select> carried. These keep
       the call sites one line each and keep the missing-element tolerance the
       optional-chained reads had. */
    function toggleOn(id) {
      return Boolean($(id)?.checked);
    }
    function setToggle(id, value, fallback = true) {
      const el = $(id);
      if (el) el.checked = boolValue(value, fallback);
    }

    function defaultHeroProfile(category, name) {
      const preset = INDUSTRY_PRESETS[category] || INDUSTRY_PRESETS.general;
      return {
        eyebrow: preset.label,
        title: name || '',
        subtitle: preset.slogan,
        primary_cta_label: 'Book a Trial',
        secondary_cta_label: 'Explore Courses',
        secondary_cta_target: 'auto',
        secondary_cta_href: '',
        show_student_login: true,
        background_style: 'soft',
        hero_image_url: ''
      };
    }

    function defaultWebsiteProfile() {
      return {
        show_principal: true,
        show_courses: true,
        show_gallery: true,
        show_faq: true,
        show_contact: true,
        show_student_area: true,
        courses_label: 'Courses & Classes',
        gallery_label: 'Student Works',
        faq_label: 'Questions & Answers',
        contact_label: 'Contact',
        // Off, and empty. Mirrors _default_website_profile() in api_v1.py —
        // a studio publishes this section by writing it, not by existing.
        show_about: false,
        about_eyebrow: { zh: '', en: '' },
        about_title: { zh: '', en: '' },
        about_body: { zh: '', en: '' },
        about_images: [],
        about_image_alts: [],
        about_items: [],
        seo_title: '',
        seo_description: ''
      };
    }

    function defaultPrincipalProfile(name) {
      return {
        show: true,
        name: '',
        title: 'Founder & Principal',
        bio: `Meet the principal behind ${name || 'the studio'} and the teaching philosophy that shapes every class.`,
        quote: 'Learn with care, confidence, and a rhythm that fits each student.',
        image_url: ''
      };
    }

    function defaultFaqItems(category) {
      const preset = INDUSTRY_PRESETS[category] || INDUSTRY_PRESETS.general;
      const label = String(preset.label || 'class').toLowerCase();
      const labelZh = String(preset.labelZh || preset.label_zh || '课程');
      // %VENUE% / %WORK% are replaced on the public page with the nouns this
      // industry uses, so the defaults stay correct for piano, dance and games.
      return [
        {
          question: { zh: '有体验课吗？', en: 'Is there a trial class?' },
          answer: {
            zh: '有的。通过报名表留下联系方式，%VENUE%会与您联系并安排合适的第一节课。',
            en: 'Yes. Leave your details on the registration form and the %VENUE% will be in touch to arrange a suitable first session.'
          }
        },
        {
          question: { zh: '课包与课时怎么算？', en: 'How do class packs work?' },
          answer: {
            zh: '课程以课包形式购买，每次上课按实际时长扣课时；余额与记录随时可在「学员专区」查询。',
            en: 'Classes are bought as packs and each session draws the credits it actually uses. Your balance and history are always visible in the student area.'
          }
        },
        {
          question: { zh: `应该选择哪个${labelZh}水平？`, en: `Which ${label} level should we choose?` },
          answer: {
            zh: '在报名表里填写当前经验与目标即可，老师会推荐合适的班型。',
            en: 'Start with your current experience and goals in the registration form, and the teacher will recommend the right class.'
          }
        },
        {
          question: { zh: '家长能看到进度吗？', en: 'Can parents view progress?' },
          answer: {
            zh: '可以。开启「学员专区」后，用姓名、手机号与%VENUE%发放的访问码即可查看课时余额与%WORK%记录。',
            en: 'Yes. When the student area is enabled, the student\'s name, mobile and the access code issued by the %VENUE% show the credit balance and %WORK% records.'
          }
        }
      ];
    }

    function defaultVisualTheme(category = $('settingCategory')?.value || 'general') {
      const preset = INDUSTRY_PRESETS[category] || INDUSTRY_PRESETS.general;
      return {
        ...(preset.visualTheme || {}),
        accent_color: $('settingPrimaryColor')?.value || preset.visualTheme?.accent_color || FALLBACK_THEME.accent_color,
        secondary_accent_color: $('settingSecondaryColor')?.value || preset.visualTheme?.secondary_accent_color || FALLBACK_THEME.secondary_accent_color
      };
    }

    function themeValue(theme, snake, fallback = '') {
      const parts = snake.split('_');
      const camel = parts[0] + parts.slice(1).map((part) => part[0].toUpperCase() + part.slice(1)).join('');
      return theme?.[snake] || theme?.[camel] || fallback;
    }

    /* The two candidates for ink on a solid fill, and the same pair
       palette_gen.build() picks between in `best_on`. Not palette values: a
       label on a colour is either near-white or near-black, and which one is a
       measurement, not a preference. */
    const ON_FILL_LIGHT = '#FFFFFF';
    const ON_FILL_DARK = '#10140A';

    function readableText(background) {
      return contrastRatio(background, ON_FILL_LIGHT) >= contrastRatio(background, ON_FILL_DARK)
        ? ON_FILL_LIGHT : ON_FILL_DARK;
    }

    function setVisualThemeFields(theme, styleId = '') {
      $('settingPrimaryColor').value = themeValue(theme, 'accent_color', FALLBACK_THEME.accent_color);
      $('settingSecondaryColor').value = themeValue(theme, 'secondary_accent_color', FALLBACK_THEME.secondary_accent_color);
      $('settingThemeBackground').value = themeValue(theme, 'background_color', FALLBACK_THEME.background_color);
      $('settingThemePanel').value = themeValue(theme, 'panel_color', FALLBACK_THEME.panel_color);
      $('settingThemeText').value = themeValue(theme, 'text_color', FALLBACK_THEME.text_color);
      $('settingThemeMuted').value = themeValue(theme, 'muted_text_color', FALLBACK_THEME.muted_text_color);
      $('settingThemeBorder').value = themeValue(theme, 'border_color', FALLBACK_THEME.border_color);
      $('settingButtonStyle').value = themeValue(theme, 'button_style', 'soft');
      $('settingFontMood').value = themeValue(theme, 'font_mood', 'modern');
      activeVisualStyle = styleId || themeValue(theme, 'style_id', '');
      activeColorScheme = themeValue(theme, 'color_scheme', 'light') === 'dark' ? 'dark' : 'light';
      /* This function is handed two different kinds of thing: a SAVED record,
         which carries the owner's scheme preference, and a GENERATED style
         palette, which cannot — a palette is a set of colours and has no
         opinion about who picks the mode.
         Treating the second like the first is what made "follow the visitor's
         device" unselectable: choosing it set the preference, then
         applyVisualStyle() called this with style.schemes[mode], the lookup
         found no scheme_preference, and the preference was overwritten with
         the mode. The control snapped back and would have SAVED the mode. */
      const preference = themeValue(theme, 'scheme_preference', '');
      if (['light', 'dark', 'system'].includes(preference)) {
        activeSchemePreference = preference;
      } else if (activeSchemePreference !== 'system') {
        activeSchemePreference = activeColorScheme;
      }
      themeMode = themeValue(theme, 'theme_mode', activeVisualStyle ? 'preset' : 'custom');
      const savedHue = theme && (theme.accent_hue ?? theme.accentHue);
      activeAccentHue = Number.isFinite(Number(savedHue)) ? Number(savedHue) : null;
      syncAccentPicker(themeValue(theme, 'accent_color', FALLBACK_THEME.accent_color));
      renderThemeGrid();
      renderStylePresetGrid();
    }

    /* ── the accent knob ──────────────────────────────────────────────────
       One colour, and only its HUE is kept. The lightness and saturation are
       the product's, solved for the contrast targets, which is what makes a
       free colour input safe to hand an owner: a fluorescent logo becomes a
       deep pine rather than a call to action nobody can read.

       The solving happens on the server. Putting a copy of the solver in this
       page to save the round trip would give the product a third
       implementation of one algorithm — there are two, and they are only safe
       because a parity test compares them token for token. */
    let activeAccentHue = null;
    let accentPreviewTimer = null;
    let accentPreviewSeq = 0;

    /* The id of the one theme whose accent is a live input rather than a
       design decision. Mirrors FREE_ACCENT_STYLE_ID in presets.py. */
    const FREE_ACCENT_STYLE_ID = 'custom';

    /* Nine cards, each showing the palette it is. The industry's recommended
       theme is badged, never auto-applied — a card is a MOOD, and choosing one
       is the studio's job. Selecting Custom is the only thing that reveals the
       colour picker. */
    function renderThemeGrid() {
      const grid = $('themeGrid');
      if (!grid) return;
      const entries = Object.entries(VISUAL_STYLE_PRESETS);
      if (!entries.length) return;
      const isZh = adminIsZh();
      const category = $('settingCategory')?.value || 'general';
      const industry = INDUSTRY_PRESETS[category] || INDUSTRY_PRESETS.general;
      const recommended = industry?.recommendedStyleId;

      const modesOf = (style) => (Array.isArray(style?.modes) && style.modes.length
        ? style.modes
        : Object.keys(style?.schemes || {}));
      /* Recommended first, then everything with both modes, then single-mode
         outliers, then Custom — which is last because it is the escape hatch,
         not a competitor to the eight. */
      const rank = ([key, style]) => {
        if (key === FREE_ACCENT_STYLE_ID) return 3;
        if (key === recommended) return 0;
        return modesOf(style).length > 1 ? 1 : 2;
      };
      const ordered = entries.slice().sort((a, b) => {
        const byRank = rank(a) - rank(b);
        return byRank || styleName(a[1]).localeCompare(
          styleName(b[1]), isZh ? 'zh-Hans-CN' : 'en');
      });

      grid.innerHTML = ordered.map(([key, style]) => {
        const light = (style.schemes && (style.schemes.light || style.schemes.dark))
          || style.visualTheme || {};
        const modes = modesOf(style);
        const flags = [];
        if (key === recommended) {
          flags.push(`<span class="theme-card-flag">${esc(isZh ? '推荐' : 'Recommended')}</span>`);
        }
        if (modes.length === 1) {
          flags.push(`<span class="theme-card-flag mode">${
            esc(modes[0] === 'dark' ? (isZh ? '仅暗色' : 'Dark only')
                                    : (isZh ? '仅明亮' : 'Light only'))}</span>`);
        }
        const paper = themeValue(light, 'background_color', FALLBACK_THEME.background_color);
        const ink = themeValue(light, 'text_color', FALLBACK_THEME.text_color);
        const muted = themeValue(light, 'muted_text_color', FALLBACK_THEME.muted_text_color);
        const strip = ['accent_color', 'secondary_accent_color', 'border_strong_color']
          .map((token) => `<i style="background:${themeValue(light, token, ink)}"></i>`).join('');
        return `<button type="button" role="radio" class="theme-card"
          data-style-key="${esc(key)}" aria-checked="${key === activeVisualStyle ? 'true' : 'false'}"
          style="--theme-card-paper:${paper};--theme-card-ink:${ink};--theme-card-muted:${muted}">
          <span class="theme-card-name"><span>${esc(styleName(style))}</span></span>
          <span class="theme-card-strip" aria-hidden="true">${/*safe*/ strip}</span>
          <span class="theme-card-mood">${esc(styleDescription(style))}</span>
          ${flags.length ? `<span class="theme-card-flags">${/*safe*/ flags.join('')}</span>` : ''}
        </button>`;
      }).join('');

      /* The picker belongs to Custom and only to Custom. Leaving it on screen
         under the eight curated cards is what made them look like decoration
         around a colour input. */
      const wrap = $('accentPickerWrap');
      if (wrap) wrap.hidden = activeVisualStyle !== FREE_ACCENT_STYLE_ID;
    }

    function syncAccentPicker(accentColor) {
      const swatch = $('accentSourceSwatch');
      const field = $('accentSourceHex');
      if (!swatch || !field) return;
      const shown = /^#[0-9a-f]{6}$/i.test(accentColor || '')
        ? accentColor.toUpperCase() : FALLBACK_THEME.accent_color.toUpperCase();
      swatch.value = shown;
      if (document.activeElement !== field) field.value = shown;
    }

    function accentNote(notes, hue) {
      const isZh = adminIsZh();
      const small = $('accentSourceNote');
      if (!small) return;
      small.classList.remove('note-unresolved', 'note-moved');
      if (notes.includes('achromatic')) {
        small.classList.add('note-moved');
        small.textContent = isZh
          ? '这个颜色几乎没有色相，已回到默认强调色——灰色的按钮会消失在页面里。'
          : 'That colour has almost no hue, so the default accent is used — a grey call to action disappears into the page.';
        return;
      }
      if (notes.includes('moved_out_of_status_band')) {
        small.classList.add('note-moved');
        small.textContent = isZh
          ? `已移到 ${Math.round(hue)}°：原色相会被读成「成功／警示／危险／提示」之一。`
          : `Moved to ${Math.round(hue)}° — the picked hue reads as a status colour (success, warning, danger or info).`;
        return;
      }
      small.textContent = isZh
        ? '只取色相，深浅由系统求解，按钮始终可读。'
        : 'Only the hue is used — the depth is solved so the button stays readable.';
    }

    async function previewAccent(source, hue = null) {
      const seq = ++accentPreviewSeq;
      try {
        /* No source and no hue means "never set" — ask with neither and let
           the endpoint supply its starting hue, rather than keeping a second
           copy of that number in this page. */
        const query = Number.isFinite(hue) ? 'hue=' + encodeURIComponent(hue)
                    : source ? 'accent=' + encodeURIComponent(source)
                    : '';
        const response = await fetch('/v1/theme-preview' + (query ? '?' + query : ''));
        if (!response.ok) return;
        const body = await response.json();
        /* A colour input fires continuously; an older reply must never land on
           top of a newer one. */
        if (seq !== accentPreviewSeq) return;
        activeAccentHue = body.hue;
        /* Solving a hue IS choosing the Custom theme; the save path only
           honours accent_hue for that style, so the two must agree. */
        activeVisualStyle = FREE_ACCENT_STYLE_ID;
        const solved = body.themes[activeColorScheme] || body.themes.light;
        if (solved) {
          $('settingPrimaryColor').value = solved.accent_color;
          $('settingSecondaryColor').value = solved.secondary_accent_color;
          $('settingThemeBackground').value = solved.background_color;
          $('settingThemePanel').value = solved.panel_color;
          $('settingThemeText').value = solved.text_color;
          $('settingThemeMuted').value = solved.muted_text_color;
          $('settingThemeBorder').value = solved.border_color;
          syncAccentPicker(solved.accent_color);
        }
        accentNote(body.notes || [], body.hue);
        renderThemeGrid();
        themeMode = 'preset';
        renderStylePresetGrid();
        setSettingsDirty(true);
        updateThemePreview();
      } catch (error) { /* offline: leave the fields as they are */ }
    }

    function previewAccentHue(hue) {
      return previewAccent(null, hue);
    }

    function requestAccentPreview(source) {
      clearTimeout(accentPreviewTimer);
      accentPreviewTimer = setTimeout(() => previewAccent(source), 180);
    }

    /* Reads the dominant colour out of the studio's own logo, which is where
       an owner's answer to "what is your colour" actually lives. Averaging is
       wrong — it turns any two-colour mark into mud — so this buckets by hue
       and takes the most-weighted bucket among the pixels that have a hue at
       all. */
    function dominantHexFromImage(image) {
      const size = 64;
      const canvas = document.createElement('canvas');
      canvas.width = canvas.height = size;
      const context = canvas.getContext('2d', { willReadFrequently: true });
      context.drawImage(image, 0, 0, size, size);
      const { data } = context.getImageData(0, 0, size, size);
      const buckets = new Map();
      for (let i = 0; i < data.length; i += 4) {
        const [r, g, b, a] = [data[i], data[i + 1], data[i + 2], data[i + 3]];
        if (a < 128) continue;
        const chroma = Math.max(r, g, b) - Math.min(r, g, b);
        if (chroma < 24) continue;                    // no hue worth counting
        const key = Math.round(rgbHue(r, g, b) / 10) * 10;
        const entry = buckets.get(key) || { weight: 0, pixels: 0, r: 0, g: 0, b: 0 };
        entry.weight += chroma;                       // chromatic pixels count more
        entry.pixels += 1;
        entry.r += r; entry.g += g; entry.b += b;
        buckets.set(key, entry);
      }
      if (!buckets.size) return '';
      let best = null;
      for (const entry of buckets.values()) if (!best || entry.weight > best.weight) best = entry;
      const toHex = (sum) => Math.round(sum / best.pixels).toString(16).padStart(2, '0');
      return ('#' + toHex(best.r) + toHex(best.g) + toHex(best.b)).toUpperCase();
    }

    function rgbHue(r, g, b) {
      const max = Math.max(r, g, b), min = Math.min(r, g, b), d = max - min;
      if (!d) return 0;
      let hue;
      if (max === r) hue = ((g - b) / d) % 6;
      else if (max === g) hue = (b - r) / d + 2;
      else hue = (r - g) / d + 4;
      hue *= 60;
      return hue < 0 ? hue + 360 : hue;
    }

    function rememberPresetState(message) {
      lastPresetSnapshot = settingsPayload();
      $('presetUndoText').textContent = message;
      $('presetUndoBar').classList.remove('hidden');
    }

    function markThemeCustom() {
      themeMode = 'custom';
      renderStylePresetGrid();
    }

    function hexToRgb(hex) {
      const clean = String(hex || '').replace('#', '');
      if (!/^[0-9a-fA-F]{6}$/.test(clean)) return null;
      return [0, 2, 4].map((idx) => parseInt(clean.slice(idx, idx + 2), 16));
    }

    function luminance(hex) {
      const rgb = hexToRgb(hex);
      if (!rgb) return 0;
      const linear = rgb.map((value) => {
        const channel = value / 255;
        return channel <= 0.03928 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
      });
      return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
    }

    function contrastRatio(hexA, hexB) {
      const lighter = Math.max(luminance(hexA), luminance(hexB));
      const darker = Math.min(luminance(hexA), luminance(hexB));
      return (lighter + 0.05) / (darker + 0.05);
    }

    /* The preview speaks the TENANT vocabulary, scoped.
     *
     * Custom properties inherit, so declaring --bg / --ink / --clay on the
     * preview element itself gives that subtree the public site's names
     * without touching the console around it. Before v8.4.0 the preview had a
     * parallel --preview-* set precisely because the console had ALSO declared
     * --bg and --ink to mean its own paper and its own navy; the two could not
     * coexist in one document, so the mock got a private dialect and a
     * --preview-paper fallback triple to go with it.
     *
     * The console no longer declares those names (they come from
     * console-theme.css, and a scoped declaration wins inside the subtree), so
     * the preview can be fed the same forty tokens the live page receives from
     * /brand, through the same map. That is what makes a dark theme previewable
     * at all: the mock used seven values and none of them were the alternating
     * band, the borders on a dark surface, or the disabled state.
     */
    const PREVIEW_TOKENS = {
      background_color:       ['--bg'],
      background_alt_color:   ['--bg2'],
      panel_color:            ['--panel', '--surface'],
      surface_hover_color:    ['--surface-hover'],
      text_color:             ['--ink'],
      text_soft_color:        ['--ink2'],
      muted_text_color:       ['--muted'],
      border_color:           ['--line'],
      border_strong_color:    ['--line-strong'],
      accent_color:           ['--clay', '--accent'],
      accent_hover_color:     ['--clay-hover', '--accent-hover'],
      accent_pressed_color:   ['--clay-pressed', '--accent-pressed'],
      accent_text_color:      ['--on-accent'],
      accent_soft_color:      ['--accent-soft'],
      accent_on_soft_color:   ['--on-accent-soft'],
      accent_border_color:    ['--accent-border'],
      secondary_accent_color: ['--clay-d', '--accent-2'],
      success_color:          ['--success'],
      warning_color:          ['--warning'],
      danger_color:           ['--danger'],
      info_color:             ['--info'],
      focus_ring_color:       ['--focus-ring'],
      disabled_surface_color: ['--disabled-surface'],
      disabled_text_color:    ['--disabled-text'],
    };

    function applyPreviewTheme(element, formValues) {
      /* The full solved theme when a curated style is selected; the six fields
         the Advanced panel exposes otherwise. Advanced is deliberately a
         smaller surface — a studio hand-picking six colours does not get the
         alternating band and the disabled state solved for it, so those fall
         back to the selected style's. */
      const style = VISUAL_STYLE_PRESETS[activeVisualStyle];
      const solved = (style?.schemes && style.schemes[activeColorScheme]) || style?.visualTheme || {};
      const override = themeMode === 'custom' ? {
        background_color: formValues.bg,
        panel_color: formValues.panel,
        text_color: formValues.ink,
        muted_text_color: formValues.muted,
        border_color: formValues.border,
        accent_color: formValues.accent,
        accent_text_color: formValues.accentText,
      } : {};
      Object.entries(PREVIEW_TOKENS).forEach(([key, names]) => {
        const camel = key.replace(/_([a-z])/g, (_, c) => c.toUpperCase());
        const value = override[key] || solved[key] || solved[camel];
        if (!value) return;
        names.forEach((name) => element.style.setProperty(name, value));
      });
    }

    function updateThemePreview() {
      const primary = $('settingPrimaryColor').value || FALLBACK_THEME.accent_color;
      const secondary = $('settingSecondaryColor').value || FALLBACK_THEME.secondary_accent_color;
      const bg = $('settingThemeBackground')?.value || FALLBACK_THEME.background_color;
      const panel = $('settingThemePanel')?.value || FALLBACK_THEME.panel_color;
      const accent = primary;
      const ink = $('settingThemeText')?.value || FALLBACK_THEME.text_color;
      const muted = $('settingThemeMuted')?.value || FALLBACK_THEME.muted_text_color;
      const border = $('settingThemeBorder')?.value || FALLBACK_THEME.border_color;
      const accentText = readableText(accent);
      const preview = $('previewDevice');
      const liveFrame = $('previewLiveFrame');
      if (preview) preview.classList.toggle('hidden', previewSource === 'live');
      if (liveFrame) {
        liveFrame.classList.toggle('hidden', previewSource !== 'live');
        liveFrame.classList.toggle('mobile', previewDevice === 'mobile');
        if (previewSource === 'live') {
          const suffix = previewMode === 'register' ? '/register' : '';
          const nextUrl = `/${encodeURIComponent(currentTenantSlug())}${suffix}?lang=${previewLanguage}`;
          if (liveFrame.getAttribute('src') !== nextUrl) liveFrame.src = nextUrl;
        }
      }
      if (preview) {
        applyPreviewTheme(preview, { bg, panel, ink, muted, border, accent, accentText });
        preview.style.setProperty('--radius', $('settingButtonStyle')?.value === 'rounded' ? '999px' : $('settingButtonStyle')?.value === 'sharp' ? '0' : '8px');
        preview.classList.toggle('mobile', previewDevice === 'mobile');
        preview.classList.toggle('mode-portal', previewMode === 'portal');
        preview.classList.toggle('mode-register', previewMode === 'register');
        preview.dataset.brandScheme = activeColorScheme;
      }
      $('themePreviewTitle').textContent = localizedValue('settingHeroTitle', 'settingHeroTitleEn', `${$('settingName').value || 'Studio'} Theme`);
      $('themePreviewSlug').textContent = currentTenantSlug() || 'tenant';
      const welcomeVisible = toggleOn('settingShowWelcome');
      $('themePreviewWelcome').textContent = welcomeVisible
        ? localizedValue('settingHeroSubtitle', 'settingHeroSubtitleEn', $('settingWelcome').value || $('settingSlogan').value || 'Welcome')
        : (previewLanguage === 'zh' ? '欢迎文案已隐藏。' : 'Welcome message is hidden.');
      $('previewName').textContent = $('settingName').value || 'Studio';
      $('previewContact').textContent = [$('settingPhone').value, $('settingEmail').value, $('settingAddress').value].filter(Boolean).join(' · ') || 'Contact details';
      const previewLogoUrl = $('settingLogoUrl').value.trim();
      $('logoPreview').hidden = !previewLogoUrl;
      $('logoPreview').alt = previewLogoUrl ? `${$('settingName').value || 'Studio'} logo` : '';
      if (previewLogoUrl) $('logoPreview').src = previewLogoUrl;
      $('previewHeroEyebrow').textContent = $('settingHeroEyebrow')?.value || $('settingCategory')?.selectedOptions?.[0]?.textContent || 'Studio';
      const heroPreviewImage = $('settingHeroImageUrl')?.value.trim();
      const previewArt = document.querySelector('.preview-art');
      if (previewArt) {
        previewArt.style.backgroundImage = heroPreviewImage
          ? `url("${heroPreviewImage.replace(/["\\]/g, '\\$&')}")`
          : '';
        previewArt.style.backgroundSize = heroPreviewImage ? 'cover' : '';
        previewArt.style.backgroundPosition = heroPreviewImage ? 'center' : '';
      }
      $('previewPrimaryCta').textContent = localizedValue('settingPrimaryCta', 'settingPrimaryCtaEn', previewLanguage === 'zh' ? '预约体验' : 'Book a Trial');
      $('previewSecondaryCta').textContent = localizedValue('settingSecondaryCta', 'settingSecondaryCtaEn', previewLanguage === 'zh' ? '查看课程' : 'Explore Courses');
      $('previewRegisterEyebrow').textContent = $('settingHeroEyebrow')?.value || 'Registration';
      $('previewRegisterTitle').textContent = localizedValue('settingRegistrationTitle', 'settingRegistrationTitleEn', previewLanguage === 'zh' ? '快速报名' : 'Quick Registration');
      $('previewRegisterIntro').textContent = localizedValue('settingRegisterIntro', 'settingRegisterIntroEn', previewLanguage === 'zh' ? '告诉我们学员的兴趣与目标。' : 'Tell us about the student and their goals.');
      renderPreviewSurfaceContract();
      renderPreviewSections();
      renderPreviewRegistrationFields();
      const issues = [];
      const bodyRatio = Math.min(contrastRatio(ink, bg), contrastRatio(ink, panel));
      const mutedRatio = Math.min(contrastRatio(muted, bg), contrastRatio(muted, panel));
      const actionRatio = contrastRatio(primary, accentText);
      if (bodyRatio < 4.5) issues.push(`Body text contrast is ${bodyRatio.toFixed(1)}:1 (needs 4.5:1).`);
      if (mutedRatio < 4.5) issues.push(`Muted text contrast is ${mutedRatio.toFixed(1)}:1 (needs 4.5:1).`);
      if (actionRatio < 4.5) issues.push(`Button text contrast is ${actionRatio.toFixed(1)}:1 (needs 4.5:1).`);
      const warning = $('colorWarning');
      if (issues.length) {
        warning.textContent = `${issues.join(' ')} Choose a curated style or adjust Advanced colours before publishing.`;
        warning.classList.remove('hidden');
      } else {
        warning.classList.add('hidden');
      }
    }

    function renderPreviewSections() {
      const box = $('previewSections');
      if (!box) return;
      box.replaceChildren();
      const modules = draftSurfaceContract?.modules || {};
      const append = (key, title, body, images = []) => {
        if (!modules[key]?.visible) return;
        const section = document.createElement('section');
        section.className = `preview-content-section preview-content-${key}`;
        section.dataset.previewSection = key;
        const copy = document.createElement('div');
        const heading = document.createElement('strong'); heading.textContent = title;
        const paragraph = document.createElement('p'); paragraph.textContent = body;
        copy.append(heading, paragraph);
        if (images.length) {
          const gallery = document.createElement('div'); gallery.className = 'preview-content-images';
          images.slice(0, 3).forEach((url) => {
            const img = document.createElement('img'); img.src = url; img.alt = ''; img.loading = 'lazy';
            img.onerror = () => img.remove(); gallery.appendChild(img);
          });
          section.append(gallery, copy);
        } else {
          section.appendChild(copy);
        }
        box.appendChild(section);
      };
      append('about',
        localizedValue('settingAboutTitle', 'settingAboutTitleEn', previewNoun('空间与体验', 'Space & experience')),
        localizedValue('settingAboutBody', 'settingAboutBodyEn', previewNoun('介绍来访者会感受到的空间、氛围与过程。', 'Describe the place, atmosphere and experience visitors can expect.')),
        aboutImages);
      append('principal', $('settingPrincipalName')?.value || previewNoun('主理人', 'Principal'),
        localizedValue('settingPrincipalBio', 'settingPrincipalBioEn', previewNoun('主理人介绍', 'Principal introduction')),
        [$('settingPrincipalImageUrl')?.value].filter(Boolean));
      append('showcase', localizedValue('settingShowcaseTitle', 'settingShowcaseTitleEn', previewNoun('工作室作品', 'Selected work')),
        localizedValue('settingShowcaseLead', 'settingShowcaseLeadEn', previewNoun('由工作室精选的代表作品。', 'A selection curated by the studio.')),
        showcaseItems.filter(showcaseHasContent).map((item) => item.image_url).filter(Boolean));
      append('courses', localizedValue('settingCoursesLabel', 'settingCoursesLabelEn', previewNoun('课程', 'Courses')),
        modules.courses?.ready ? previewNoun('已发布课程将显示在这里。', 'Published programs appear here.') : previewNoun('尚无已发布课程。', 'No published programs yet.'));
      append('gallery', localizedValue('settingGalleryLabel', 'settingGalleryLabelEn', previewNoun('学员作品', 'Student works')),
        modules.gallery?.ready ? previewNoun('已授权的学员作品将显示在这里。', 'Consented student work appears here.') : previewNoun('尚无已授权作品。', 'No consented work yet.'));
      append('faq', localizedValue('settingFaqLabel', 'settingFaqLabelEn', previewNoun('常见问答', 'FAQ')),
        previewNoun(`${collectFaqItems().length} 条问答`, `${collectFaqItems().length} questions`));
      append('contact', localizedValue('settingContactLabel', 'settingContactLabelEn', previewNoun('联系我们', 'Contact')),
        [$('settingEmail')?.value, $('settingPhone')?.value, $('settingAddress')?.value].filter(Boolean).join(' · '));
    }

    function renderPreviewSurfaceContract() {
      const nav = $('previewNav');
      const footer = $('previewFooterLinks');
      if (!nav || !footer || !window.StudioSaaS.publicSurface) return;
      const payload = settingsPayload();
      // The editor's own records, not collectShowcaseItems() — that one maps to
      // the API's camelCase on its way out, so `image_url` and
      // `publication_state` are both undefined by the time this filter reads
      // them. showcaseHasContent() therefore answered false for every work, and
      // the draft said "no published work yet" to a studio whose site was
      // showing two. The counter above the dropzone read from the raw records
      // and was right, which is how the two disagreed on one screen.
      const activeShowcase = showcaseItems.filter((item) => showcaseHasContent(item)
        && normalizeShowcasePublicationState(item.publication_state) === 'active');
      const faqItems = collectFaqItems();
      const liveModules = publishedSurfaceContract?.modules || {};
      const facts = Object.fromEntries(['courses', 'gallery', 'timetable']
        .map((key) => [key, Boolean(liveModules[key]?.ready)]));
      const contract = window.StudioSaaS.publicSurface.resolve({
        slug: currentTenantSlug(),
        brand: {
          name: payload.name,
          contactPhone: payload.contactPhone,
          contactEmail: payload.contactEmail,
          address: payload.address,
          websiteProfile: payload.websiteProfile,
          principalProfile: payload.principalProfile,
          heroProfile: payload.heroProfile,
          faqItems,
          registrationProfile: payload.registrationProfile,
        },
        showcase: { enabled: payload.websiteProfile.showShowcase, items: activeShowcase, total: activeShowcase.length },
        moduleFacts: facts,
        timetable: { enabled: Boolean(facts.timetable), days: [] },
      });
      draftSurfaceContract = contract;
      const labels = {
        principal: ['主理人', 'Principal'], showcase: ['工作室作品', 'Selected Work'],
        courses: ['课程', 'Courses'], timetable: ['课程安排', 'Timetable'],
        gallery: ['学员作品', 'Student Works'], faq: ['常见问答', 'FAQ'],
        student: ['学员专区', 'Student Login'], register: ['预约体验', 'Book a Trial'],
      };
      nav.replaceChildren();
      contract.navigation.forEach((module) => {
        const label = labels[module.key] || [module.key, module.key];
        const node = document.createElement(module.visible ? 'a' : 'span');
        node.textContent = adminIsZh() ? label[0] : label[1];
        node.dataset.surfaceKey = module.key;
        node.title = module.visible ? '' : adminText('公开页面尚未准备好。', 'Public surface is not ready yet.');
        if (module.visible) {
          // Same contract-key-is-not-an-address rule as public-surface.js:
          // `#home:courses` names a surface and an anchor, and only the second
          // half is a fragment a browser can resolve.
          node.href = /^#[^:]+:/.test(module.href || '')
            ? '#' + module.href.slice(module.href.indexOf(':') + 1)
            : module.href;
          node.dataset.surfaceReady = 'true';
        } else {
          node.className = 'preview-nav-unavailable';
        }
        nav.appendChild(node);
      });
      footer.replaceChildren();
      contract.footer.filter((module) => module.visible).forEach((module) => {
        const label = labels[module.key] || [module.key, module.key];
        const link = document.createElement('a');
        link.href = module.href;
        link.textContent = adminIsZh() ? label[0] : label[1];
        footer.appendChild(link);
      });
      if (!footer.children.length) {
        const empty = document.createElement('span');
        empty.textContent = localiseAdminText('The public page is not ready yet.');
        footer.appendChild(empty);
      }
      const secondary = contract.actions?.secondary;
      $('previewSecondaryCta').hidden = !secondary?.visible;
      $('previewSecondaryCta').title = secondary?.visible ? secondary.href : adminText('目标内容尚未准备好。', 'The destination is not ready yet.');
      renderPublishReadiness(contract);
    }

    /* The contract answers in identifiers because two implementations read it.
       A studio owner reads sentences. `no_consented_student_work` is the one
       that matters most: it is not a fault, it is a consent the studio has not
       been given yet, and saying so stops the switch looking broken. */
    const SURFACE_MODULE_NAMES = {
      about: ['空间与体验', 'Space & experience'],
      principal: ['主理人', 'Principal'],
      showcase: ['工作室作品', 'Selected work'],
      courses: ['课程', 'Courses'],
      timetable: ['公开课表', 'Public timetable'],
      gallery: ['学员作品', 'Student work'],
      faq: ['常见问题', 'FAQ'],
      contact: ['联系方式', 'Contact details'],
      student: ['学员专区', 'Student area'],
      register: ['报名', 'Registration'],
    };
    const SURFACE_REASONS = {
      ready: ['已在网站上显示', 'Shown on the website'],
      disabled_by_owner: ['已关闭', 'Switched off'],
      no_content: ['还没有内容', 'Nothing to show yet'],
      missing_content: ['还没有内容', 'Nothing to show yet'],
      missing_about_content: ['还没有标题、正文或照片', 'No title, text or photo yet'],
      no_published_courses: ['还没有已发布的课程', 'No published course yet'],
      no_published_works: ['还没有已发布的作品', 'No published work yet'],
      not_published: ['还没有发布', 'Not published yet'],
      no_upcoming_classes: ['接下来这几周没有公开课', 'No public class in the weeks shown'],
      no_consented_student_work: ['还没有学员同意公开作品', 'No student has agreed to show their work yet'],
      no_faq_content: ['还没有问答', 'No question and answer yet'],
      missing_contact_details: ['还没有填联系方式', 'No contact details yet'],
      registration_unavailable: ['报名资料还不完整', 'The registration profile is incomplete'],
    };
    const SURFACE_NEXT_ACTIONS = {
      complete_space_profile: ['补一个标题、一段正文或一张照片', 'Add a title, some text or a photo'],
      add_principal_bio: ['写一段主理人简介', 'Write the principal a short introduction'],
      publish_showcase_work: ['在「工作室作品」里发布一件作品', 'Publish a piece under Selected work'],
      publish_course: ['在 CMS 里发布一门课程', 'Publish a course in the CMS'],
      publish_timetable: ['在 CMS 里勾选要公开的课', 'Tick the classes to show, in the CMS'],
      share_student_work: ['等学员同意后再公开', 'Wait until a student agrees'],
      add_faq: ['写一条常见问题', 'Add a question and answer'],
      add_contact_details: ['填一个电话、邮箱或地址', 'Add a phone, email or address'],
      complete_registration_profile: ['把报名表填完整', 'Complete the registration form'],
      review_in_studio_admin: ['', ''],
    };

    function surfaceStateSentence(module) {
      if (!module) return ['状态未知', 'Status unknown'];
      const reason = SURFACE_REASONS[module.reasonCode] || ['还不能显示', 'Not ready to show'];
      if (module.visible || !module.intent) return reason;
      const next = SURFACE_NEXT_ACTIONS[module.nextAction] || ['', ''];
      if (!next[0]) return reason;
      return [`${reason[0]} · ${next[0]}`, `${reason[1]} — ${next[1]}`];
    }

    function renderSurfaceSwitchStates(contract) {
      document.querySelectorAll('[data-surface-state]').forEach((node) => {
        const module = contract?.modules?.[node.dataset.surfaceState];
        const sentence = surfaceStateSentence(module);
        node.textContent = adminIsZh() ? sentence[0] : sentence[1];
        node.dataset.tone = module?.visible ? 'ready' : module?.intent ? 'blocked' : 'off';
      });
    }

    function renderPublishReadiness(contract) {
      renderSurfaceSwitchStates(contract);
      const box = $('publishReadinessList');
      if (!box) return;
      box.replaceChildren();
      Object.values(contract?.modules || {}).filter((module) => module.intent).forEach((module) => {
        const row = document.createElement('div');
        row.className = module.visible ? 'ready' : 'blocked';
        const name = SURFACE_MODULE_NAMES[module.key] || [module.key, module.key];
        const sentence = surfaceStateSentence(module);
        row.textContent = `${module.visible ? '✓' : '△'} ${adminIsZh() ? name[0] : name[1]} · ${adminIsZh() ? sentence[0] : sentence[1]}`;
        box.appendChild(row);
      });
    }

    function renderPreviewRegistrationFields() {
      const box = $('previewRegisterFields');
      if (!box) return;
      const profile = collectRegistrationProfile();
      box.innerHTML = profile.fields.slice(0, 5).map((field) => `
        <div class="preview-field">${esc((previewLanguage === 'zh' ? field.label_zh : field.label_en) || field.label || field.key || 'Question')}${field.required ? ' *' : ''}</div>
      `).join('');
    }

    function fillRegistrationFields(profile) {
      const fallback = defaultRegistrationProfile($('settingCategory')?.value || 'general');
      const fields = Array.isArray(profile?.fields) && profile.fields.length ? profile.fields : fallback.fields;
      $('registrationFieldsEditor').innerHTML = fields.map((field, index) => `
        <div class="question-card" data-registration-card="${index}">
          <div class="form-group">
            <label for="regLabelEn${index}">Label · English</label>
            <input id="regLabelEn${index}" data-reg-label="${index}" value="${esc(field.label_en || field.label || field.key || 'Field')}">
            <input type="hidden" data-reg-key="${index}" value="${esc(field.key || `field${index + 1}`)}">
          </div>
          <div class="form-group">
            <label for="regLabelZh${index}">Label · 中文</label>
            <input id="regLabelZh${index}" data-reg-label-zh="${index}" value="${esc(field.label_zh || field.label || field.key || '问题')}">
          </div>
          <div class="form-group">
            <label for="regPlaceholderEn${index}">Placeholder · English</label>
            <input id="regPlaceholderEn${index}" data-reg-placeholder="${index}" value="${esc(field.placeholder_en || field.placeholder || '')}">
          </div>
          <div class="form-group">
            <label for="regPlaceholderZh${index}">Placeholder · 中文</label>
            <input id="regPlaceholderZh${index}" data-reg-placeholder-zh="${index}" value="${esc(field.placeholder_zh || field.placeholder || '')}">
          </div>
          <div class="form-group">
            <label for="regType${index}">Type</label>
            <select id="regType${index}" data-reg-type="${index}">
              ${[['text', 'Short text'], ['textarea', 'Long text'], ['select', 'Dropdown']].map(([type, label]) => `<option value="${type}" ${type === (field.type || 'text') ? 'selected' : ''}>${label}</option>`).join('')}
            </select>
          </div>
          <div class="form-group">
            <label for="regRequired${index}">Required / Options</label>
            <select id="regRequired${index}" data-reg-required="${index}">
              <option value="false" ${!field.required ? 'selected' : ''}>Optional</option>
              <option value="true" ${field.required ? 'selected' : ''}>Required</option>
            </select>
            <input data-reg-options="${index}" style="margin-top:8px" value="${esc((field.options || []).join(', '))}" placeholder="Select options, comma separated" aria-label="Select options, comma separated">
            <button type="button" class="btn-secondary btn-sm" style="margin-top:8px" data-remove-registration="${index}">Remove</button>
          </div>
        </div>
      `).join('');
    }

    function collectRegistrationProfile() {
      const fallback = defaultRegistrationProfile($('settingCategory').value);
      const fields = [];
      $('registrationFieldsEditor').querySelectorAll('[data-reg-label]').forEach((input, index) => {
        const selectorKey = input.getAttribute('data-reg-label') || String(index);
        const label = input.value.trim();
        const labelZh = $('registrationFieldsEditor').querySelector(`[data-reg-label-zh="${selectorKey}"]`)?.value.trim() || label;
        const key = $('registrationFieldsEditor').querySelector(`[data-reg-key="${selectorKey}"]`)?.value || `field${index + 1}`;
        const placeholder = $('registrationFieldsEditor').querySelector(`[data-reg-placeholder="${selectorKey}"]`)?.value || '';
        const placeholderZh = $('registrationFieldsEditor').querySelector(`[data-reg-placeholder-zh="${selectorKey}"]`)?.value || placeholder;
        const type = $('registrationFieldsEditor').querySelector(`[data-reg-type="${selectorKey}"]`)?.value || 'text';
        const required = $('registrationFieldsEditor').querySelector(`[data-reg-required="${selectorKey}"]`)?.value === 'true';
        const options = ($('registrationFieldsEditor').querySelector(`[data-reg-options="${selectorKey}"]`)?.value || '')
          .split(',')
          .map((item) => item.trim())
          .filter(Boolean);
        if (label) fields.push({
          key, label, label_en: label, label_zh: labelZh,
          placeholder, placeholder_en: placeholder, placeholder_zh: placeholderZh,
          type, required, options
        });
      });
      const titleZh = $('settingRegistrationTitle').value.trim();
      const titleEn = $('settingRegistrationTitleEn').value.trim();
      const fallbackTitle = fallback.title && typeof fallback.title === 'object'
        ? fallback.title
        : { zh: String(fallback.title || ''), en: String(fallback.title || '') };
      return {
        title: {
          zh: titleZh || titleEn || fallbackTitle.zh,
          en: titleEn || titleZh || fallbackTitle.en
        },
        fields: fields.length ? fields : fallback.fields
      };
    }

    /* FAQ copy is stored per language. It used to be one string per field, so
     * the portal's EN switch could never reach the FAQ — the API had nowhere to
     * put a second language. A legacy single string is shown in both boxes. */
    function faqText(value, language) {
      if (value && typeof value === 'object') return value[language] || value.zh || value.en || '';
      return String(value || '');
    }

    function fillFaqItems(items) {
      const fallback = defaultFaqItems($('settingCategory')?.value || 'general');
      const faqs = Array.isArray(items) && items.length ? items : fallback;
      $('faqItemsEditor').innerHTML = faqs.slice(0, 6).map((item, index) => `
        <div class="faq-card" data-faq-card="${index}">
          <div class="form-group">
            <label for="faqQuestionZh${index}">Question (中文)</label>
            <input id="faqQuestionZh${index}" data-faq-question="${index}" value="${esc(faqText(item.question, 'zh'))}">
            <label class="mt-2" for="faqQuestionEn${index}">Question (English)</label>
            <input id="faqQuestionEn${index}" data-faq-question-en="${index}" value="${esc(faqText(item.question, 'en'))}">
            <button type="button" class="btn-secondary btn-sm" style="margin-top:8px" data-remove-faq="${index}">Remove</button>
          </div>
          <div class="form-group">
            <label for="faqAnswerZh${index}">Answer (中文)</label>
            <textarea id="faqAnswerZh${index}" data-faq-answer="${index}" rows="3">${esc(faqText(item.answer, 'zh'))}</textarea>
            <label class="mt-2" for="faqAnswerEn${index}">Answer (English)</label>
            <textarea id="faqAnswerEn${index}" data-faq-answer-en="${index}" rows="3">${esc(faqText(item.answer, 'en'))}</textarea>
          </div>
        </div>
      `).join('');
    }

    /* Family-facing message templates (P1-8). Defaults mirror
       _default_message_templates() in api_v1.py. */
    const MESSAGE_FIELDS = {
      checkin: 'messageCheckin',
      checkin_empty: 'messageCheckinEmpty',
      topup: 'messageTopup',
      renewal: 'messageRenewal',
      birthday: 'messageBirthday'
    };
    function defaultMessageTemplates() {
      return {
        checkin: '{student} 今日已完成签到 ✓ 当前剩余 {balance} 课时。{studio} 感谢您的支持！',
        checkin_empty: '{student} 今日已完成签到 ✓ 当前剩余 0 课时，已用完，欢迎联系老师续课～',
        topup: '{student} 您好！已为您成功充值 {credits} 课时{fee}，当前账户共 {balance} 课时。感谢您对 {studio} 的信任！',
        renewal: '{student} 家长您好！温馨提醒：您在 {studio} 的剩余课时为 {balance} 节{note}，为不影响后续上课安排，欢迎随时联系老师续课。',
        birthday: '{student} 您好！{studio} 全体老师祝您生日快乐！愿您在新的一岁里灵感不断、收获满满～'
      };
    }
    function fillMessageTemplates(templates) {
      const defaults = defaultMessageTemplates();
      const source = templates && typeof templates === 'object' ? templates : {};
      Object.entries(MESSAGE_FIELDS).forEach(([key, id]) => {
        const field = $(id);
        if (field) field.value = source[key] || defaults[key];
      });
    }
    function collectMessageTemplates() {
      const defaults = defaultMessageTemplates();
      const out = {};
      Object.entries(MESSAGE_FIELDS).forEach(([key, id]) => {
        out[key] = ($(id)?.value || '').trim() || defaults[key];
      });
      return out;
    }

    function collectFaqItems() {
      const items = [];
      const editor = $('faqItemsEditor');
      editor.querySelectorAll('[data-faq-question]').forEach((input, index) => {
        const key = input.getAttribute('data-faq-question') || String(index);
        const pick = (attr) => editor.querySelector(`[${attr}="${key}"]`)?.value.trim() || '';
        const questionZh = input.value.trim();
        const questionEn = pick('data-faq-question-en');
        const answerZh = pick('data-faq-answer');
        const answerEn = pick('data-faq-answer-en');
        // One filled language is enough; it is used for both rather than
        // letting the other language fall back to template sample copy.
        const question = questionZh || questionEn;
        const answer = answerZh || answerEn;
        if (question && answer) {
          items.push({
            question: { zh: questionZh || questionEn, en: questionEn || questionZh },
            answer: { zh: answerZh || answerEn, en: answerEn || answerZh }
          });
        }
      });
      return items.length ? items : defaultFaqItems($('settingCategory').value);
    }

    function addRegistrationQuestion() {
      const profile = collectRegistrationProfile();
      const index = profile.fields.length + 1;
      profile.fields.push({
        key: `customQuestion${index}`,
        label: `Question ${index}`,
        placeholder: '',
        type: 'text',
        required: false,
        options: []
      });
      fillRegistrationFields(profile);
      setSettingsDirty(true);
      updateThemePreview();
    }

    function removeRegistrationQuestion(index) {
      const profile = collectRegistrationProfile();
      if (profile.fields.length <= 1) {
        showToast('At least one registration question is required.', 'warning');
        return;
      }
      profile.fields.splice(Number(index), 1);
      fillRegistrationFields(profile);
      setSettingsDirty(true);
      updateThemePreview();
    }

    function addFaqItem() {
      const items = collectFaqItems();
      items.push({ question: `Question ${items.length + 1}`, answer: 'Answer this clearly for parents before they enquire.' });
      fillFaqItems(items);
      setSettingsDirty(true);
      updateThemePreview();
    }

    function removeFaqItem(index) {
      const items = collectFaqItems();
      if (items.length <= 1) {
        showToast('At least one FAQ item is required.', 'warning');
        return;
      }
      items.splice(Number(index), 1);
      fillFaqItems(items);
      setSettingsDirty(true);
      updateThemePreview();
    }

    function renderPresetGrid(selected) {
      const grid = $('presetGrid');
      if (!grid) return;
      grid.innerHTML = Object.entries(INDUSTRY_PRESETS).map(([key, preset]) => {
        /* 3-2: the top-left slug used to be key.slice(0,3) — "GEN" and "GAM"
           differ by one letter at 10px, and "DAN"/"LAN" told an owner nothing
           the name below did not already say. The card leads with the industry
           name.
           4-1: the tagline follows the console language, so the card is no
           longer 「艺术 / Art / Create boldly. Grow visibly.」 all at once.
           v8.5.0: the accent dot and the three-colour swatch bar are gone.
           They were telling an owner "this industry comes with this palette",
           which stopped being true — an industry brings the vocabulary and the
           forms, and the colour is a separate choice one step below. Eight
           cards each showing the same three swatches was noise pretending to
           be information. */
        const primary = adminIsZh() ? (preset.labelZh || preset.label) : preset.label;
        const secondary = adminIsZh() ? (preset.labelZh ? preset.label : '') : (preset.labelZh || '');
        return `
        <button type="button" class="preset-card ${key === selected ? 'active' : ''}" data-preset-key="${key}" aria-pressed="${key === selected ? 'true' : 'false'}">
          <div class="preset-card-top"><span class="preset-check" aria-hidden="true">✓</span></div>
          <div><div class="preset-name">${esc(primary)}${secondary ? `<span data-no-translate>${esc(secondary)}</span>` : ''}</div><div class="preset-copy">${esc(industrySlogan(preset))}</div>${industryStarterCourse(preset) ? `<div class="preset-operation">${adminIsZh() ? '建议起步课程' : 'Starter course'} · ${esc(industryStarterCourse(preset))}</div>` : ''}</div>
        </button>
      `}).join('');
    }

    function renderStylePresetGrid() {
      const select = $('stylePresetSelect');
      if (!select) return;
      const entries = Object.entries(VISUAL_STYLE_PRESETS);
      if (!entries.length) return;
      const category = $('settingCategory')?.value || 'general';
      const industry = INDUSTRY_PRESETS[category] || INDUSTRY_PRESETS.general;
      const recommended = industry?.recommendedStyleId;
      const isZh = adminIsZh();
      if (!activeVisualStyle || !VISUAL_STYLE_PRESETS[activeVisualStyle]) activeVisualStyle = recommended || entries[0][0];
      /* 4-2: the list was in dictionary order, so an art studio opened the
         dropdown on "Arcade Lime" — a dark-only neon games theme. Order is now
         the order an owner should consider them in: the industry's recommended
         theme, then everything that offers both light and dark, then the
         dark-only outlier. Ties keep their display name's order so the list
         does not reshuffle between renders. */
      const modeCount = (style) => {
        const declared = Array.isArray(style?.modes) ? style.modes.length : 0;
        if (declared) return declared;
        return style?.schemes && typeof style.schemes === 'object' ? Object.keys(style.schemes).length : 0;
      };
      const rank = ([key, style]) => {
        if (key === recommended) return 0;
        const count = modeCount(style);
        if (count > 1) return 1;
        if (count === 1) return 2;
        return 1; // unknown mode data: do not demote a theme on missing data
      };
      const ordered = entries.slice().sort((a, b) => {
        const byRank = rank(a) - rank(b);
        if (byRank) return byRank;
        return styleName(a[1]).localeCompare(styleName(b[1]), isZh ? 'zh-Hans-CN' : 'en');
      });
      const modeSuffix = (style) => {
        const count = modeCount(style);
        if (count !== 1) return '';
        const only = (Array.isArray(style?.modes) && style.modes[0]) || Object.keys(style?.schemes || {})[0];
        return only === 'dark' ? (isZh ? '（仅暗色）' : ' (dark only)') : (isZh ? '（仅明亮）' : ' (light only)');
      };
      select.innerHTML = ordered.map(([key, style]) => `<option value="${key}" ${key === activeVisualStyle ? 'selected' : ''}>${esc(styleName(style))}${esc(modeSuffix(style))}${key === recommended ? (isZh ? ' — 推荐' : ' — Recommended') : ''}</option>`).join('');
      select.value = activeVisualStyle;

      const selected = VISUAL_STYLE_PRESETS[activeVisualStyle] || entries[0][1];
      const selectedName = styleName(selected);
      /* 1-2: `modes` used to fall back to ['light'] whenever it was absent, and
         the note below then told the owner the theme "ships light only — its
         accent cannot reach readable contrast on the other surface". For a
         stale or cached API response that sentence was invented. Missing data
         and a genuinely single-mode theme are now different states:
         `schemes` keys are real evidence, an absent list is unknown. */
      const declaredModes = Array.isArray(selected.modes) && selected.modes.length ? selected.modes.slice() : [];
      const schemeModes = selected.schemes && typeof selected.schemes === 'object' ? Object.keys(selected.schemes) : [];
      const knownModes = declaredModes.length ? declaredModes : schemeModes;
      const modesKnown = knownModes.length > 0;
      const modes = modesKnown ? knownModes : ['light', 'dark'];
      if (!modes.includes(activeColorScheme)) activeColorScheme = modes[0];
      const schemeSelect = $('settingColorScheme');
      if (schemeSelect) {
        /* `system` hands the choice to the visitor and so needs BOTH palettes
           published. A single-mode theme cannot offer it — arcade-lime is dark
           only because its accent turns olive on a light page — so it is
           disabled here for the same reason the server rejects it. */
        const bothModes = modes.length > 1;
        const options = [
          ['light', isZh ? '明亮' : 'Light', modes.includes('light')],
          ['dark', isZh ? '暗色' : 'Dark', modes.includes('dark')],
          ['system', isZh ? '跟随访客设备' : "Follow the visitor's device", bothModes],
        ];
        schemeSelect.innerHTML = options.map(([value, label, available]) => {
          const why = value === 'system'
            ? (isZh ? '（此主题只有一种模式）' : ' (needs both modes)')
            : (isZh ? '（此主题不提供）' : ' (not offered)');
          return `<option value="${value}"${available ? '' : ' disabled'}`
               + `${value === activeSchemePreference ? ' selected' : ''}>`
               + `${label}${available ? '' : why}</option>`;
        }).join('');
        schemeSelect.value = activeSchemePreference;
        const note = $('colorSchemeNote');
        if (note) {
          note.classList.toggle('note-unresolved', !modesKnown);
          if (!modesKnown) {
            note.textContent = isZh
              ? '这套主题的明暗模式信息还没读到（可能是缓存的旧接口响应）。刷新页面后再确认，先不要据此保存。'
              : "This theme's light/dark availability has not loaded — likely a cached API response. Refresh before relying on it.";
          } else if (activeSchemePreference === 'system') {
            note.textContent = isZh
              ? '官网会跟随访客设备的深色设置切换，两套配色都会发布。'
              : "The site follows each visitor's device setting; both palettes are published.";
          } else if (bothModes) {
            note.textContent = isZh
              ? '明暗为成对设计，两种模式都已通过对比度检查。'
              : 'Light and dark are designed as a pair; both are checked for contrast.';
          } else {
            note.textContent = isZh
              ? `${selectedName}仅提供${modes[0] === 'dark' ? '暗色' : '明亮'}模式——它的强调色在另一种底色上无法达到可读对比度。`
              : `${selectedName} ships ${modes[0]} only — its accent cannot reach readable contrast on the other surface.`;
          }
        }
      }
      const baseTheme = (selected.schemes && selected.schemes[activeColorScheme]) || selected.visualTheme || {};
      const custom = themeMode === 'custom';
      const shownTheme = custom ? {
        background_color: $('settingThemeBackground')?.value,
        panel_color: $('settingThemePanel')?.value,
        text_color: $('settingThemeText')?.value,
        muted_text_color: $('settingThemeMuted')?.value,
        accent_color: $('settingPrimaryColor')?.value,
        secondary_accent_color: $('settingSecondaryColor')?.value,
      } : baseTheme;
      /* 4-4: three chips showed page / accent / support only, so the two tokens
         the redesign exists for — the >=3:1 control boundary and the focus ring
         — plus the three semantic colours were invisible in the one place an
         owner compares themes. Each chip is labelled, because an unlabelled
         swatch strip is decoration. */
      /* Split by role, not by whether the colour moves. Status colours used to
         be near-identical across presets, so this second row carried a note
         explaining why three of nine chips looked the same. Since the palette
         generator started pulling their saturation toward each theme's accent
         they do differ per theme, and that note became false — the row stays
         because success/warning/danger answer a different question than the
         surface and brand colours, but the heading now says so. */
      const themedSwatches = [
        ['background_color', 'Page', '页面'],
        ['panel_color', 'Panel', '面板'],
        ['accent_color', 'Accent', '强调色'],
        ['secondary_accent_color', 'Support', '辅助色'],
        ['border_strong_color', 'Control boundary', '控件边界'],
        ['focus_ring_color', 'Focus ring', '聚焦环'],
      ];
      const statusSwatches = [
        ['success_color', 'Success', '成功'],
        ['warning_color', 'Warning', '警示'],
        ['danger_color', 'Danger', '危险'],
      ];
      const renderSwatches = (list) => list.map(([name, labelEn, labelZh]) => {
        const value = themeValue(shownTheme, name, themeValue(baseTheme, name, ''));
        if (!value) return '';
        const label = isZh ? labelZh : labelEn;
        return `<span class="swatch" title="${esc(label)} · ${esc(value)}"><i style="background:${value}"></i><small>${esc(label)}</small></span>`;
      }).filter(Boolean).join('');
      const statusLabel = isZh ? '状态色 · 已按本主题调校' : 'Status colours · tuned to this theme';
      /* renderSwatches returns markup whose every interpolated value already
         went through esc() above; the checker cannot see through the call, so
         the composition is marked rather than double-escaped. */
      $('themePalettePreview').innerHTML =
        `<div class="swatch-row">${/*safe*/ renderSwatches(themedSwatches)}</div>`
        + `<p class="swatch-group-note">${esc(statusLabel)}</p>`
        + `<div class="swatch-row">${/*safe*/ renderSwatches(statusSwatches)}</div>`;
      $('themePresetName').textContent = selectedName;
      /* 4-3: the colour relationship is the reason to prefer one palette over
         another, and it was already on the wire. */
      const harmony = harmonyName(selected);
      const harmonyChip = $('themeHarmonyChip');
      if (harmonyChip) {
        harmonyChip.textContent = harmony;
        harmonyChip.title = isZh ? '色相关系' : 'Colour relationship';
        harmonyChip.hidden = !harmony || custom;
      }
      $('themePresetDescription').textContent = custom
        ? (isZh ? `基于${selectedName}微调；行业内容保持不变。` : `Customised from ${selectedName}. Your industry content remains unchanged.`)
        : styleDescription(selected);
      $('themePresetBadge').textContent = window.AdminI18n?.translate(custom ? 'Custom' : activeVisualStyle === recommended ? 'Recommended' : 'Selected') || (custom ? 'Custom' : activeVisualStyle === recommended ? 'Recommended' : 'Selected');
      $('themePresetBadge').classList.toggle('custom', custom);
      /* The "recommended theme for your industry" note went with the eight
         industry palettes. An industry no longer recommends a colour; it
         brings the vocabulary and the forms. The accent knob writes its own
         note (see accentNote), which says the one thing an owner needs: what,
         if anything, the solver did to the colour they picked. */
      const preview = $('stylePresetPreview');
      preview.style.setProperty('--theme-panel', themeValue(shownTheme, 'panel_color', FALLBACK_THEME.panel_color));
      preview.style.setProperty('--theme-text', themeValue(shownTheme, 'text_color', FALLBACK_THEME.text_color));
      preview.style.setProperty('--theme-muted', themeValue(shownTheme, 'muted_text_color', FALLBACK_THEME.muted_text_color));
      preview.style.setProperty('--theme-accent', themeValue(shownTheme, 'accent_color', FALLBACK_THEME.accent_color));
    }

    const WORKBENCH_TABS = Object.freeze([
      'brand', 'hero', 'website', 'about', 'principal', 'showcase', 'faq',
      'register', 'timetable', 'messages', 'advanced', 'analytics'
    ]);

    /* Stable links such as ?view=register and ?view=messages let a shortcut,
       browser history or a support handoff open the exact workbench panel. */
    function requestedWorkbenchTab() {
      const value = new URLSearchParams(window.location.search).get('view');
      return WORKBENCH_TABS.includes(value) ? value : 'brand';
    }

    function switchWorkbenchTab(tab, { syncUrl = true, focus = false } = {}) {
      if (!WORKBENCH_TABS.includes(tab)) return;
      document.querySelectorAll('[data-workbench-tab]').forEach((button) => {
        const active = button.dataset.workbenchTab === tab;
        button.classList.toggle('active', active);
        button.setAttribute('aria-selected', active ? 'true' : 'false');
        button.tabIndex = active ? 0 : -1;
        if (focus && active) button.focus();
      });
      document.querySelectorAll('[data-workbench-panel]').forEach((panel) => {
        const active = panel.dataset.workbenchPanel === tab;
        panel.classList.toggle('active', active);
        panel.hidden = !active;
        panel.setAttribute('aria-hidden', active ? 'false' : 'true');
      });
      if (syncUrl) {
        const url = new URL(window.location.href);
        if (url.searchParams.get('view') !== tab) {
          url.searchParams.set('view', tab);
          window.history.pushState({ workbenchTab: tab }, '', url);
        }
      }
      if (tab === 'analytics') {
        loadAnalytics().catch((err) => showToast(`Analytics failed to load: ${err.message}`, 'error'));
        loadAuditLogs(); // renders its own error state inside the panel
      }
    }

    function switchPreviewMode(mode) {
      previewMode = mode;
      document.querySelectorAll('[data-preview-mode]').forEach((button) => {
        const active = button.dataset.previewMode === mode;
        button.classList.toggle('active', active);
        button.setAttribute('aria-pressed', String(active));
      });
      updateThemePreview();
    }

    function switchPreviewSource(source) {
      previewSource = source === 'live' ? 'live' : 'draft';
      document.querySelectorAll('[data-preview-source]').forEach((button) => {
        const active = button.dataset.previewSource === previewSource;
        button.classList.toggle('active', active);
        button.setAttribute('aria-pressed', String(active));
      });
      updateThemePreview();
    }

    function switchPreviewDevice(device) {
      previewDevice = device;
      document.querySelectorAll('[data-preview-device]').forEach((button) => {
        const active = button.dataset.previewDevice === device;
        button.classList.toggle('active', active);
        button.setAttribute('aria-pressed', String(active));
      });
      updateThemePreview();
    }

    function switchPreviewLanguage(language, {manual = false} = {}) {
      if (manual) previewLanguageManuallySet = true;
      previewLanguage = language === 'en' ? 'en' : 'zh';
      document.querySelectorAll('[data-preview-language]').forEach((button) => {
        const active = button.dataset.previewLanguage === previewLanguage;
        button.classList.toggle('active', active);
        button.setAttribute('aria-pressed', String(active));
      });
      updateThemePreview();
    }

    function fillSettings() {
      const t = tenant || {};
      const category = t.category || t.settings?.category || 'general';
      const preset = INDUSTRY_PRESETS[category] || INDUSTRY_PRESETS.general;
      const hero = t.hero_profile || t.heroProfile || defaultHeroProfile(category, t.name);
      const website = t.website_profile || t.websiteProfile || defaultWebsiteProfile();
      const principal = t.principal_profile || t.principalProfile || defaultPrincipalProfile(t.name);
      const visual = t.visual_theme || t.visualTheme || defaultVisualTheme(category);
      const localized = snakeLocalizedCopy(t.localized_copy || t.localizedCopy);
      $('studioName').textContent = t.name || 'Studio Admin';
      /* The h1 may truncate at its CSS bound or hide beside a logo on a
         phone; the full name stays reachable on the element itself. */
      $('studioName').title = t.name || '';
      $('studioFooterName').textContent = t.name || 'Studio';
      const rawStudioLogoUrl = t.logo_url || t.logoUrl || '';
      const studioLogoUrl = ['/logo.png', '/logo-light.png', '/favicon.svg'].includes(rawStudioLogoUrl)
        ? ''
        : rawStudioLogoUrl;
      const studioLogo = $('studioLogo');
      const headerBrand = studioLogo.closest('.brand');
      studioLogo.hidden = !studioLogoUrl;
      studioLogo.alt = studioLogoUrl ? `${t.name || 'Studio'} logo` : '';
      if (studioLogoUrl) studioLogo.src = studioLogoUrl;
      if (headerBrand) headerBrand.classList.toggle('brand-with-logo', Boolean(studioLogoUrl));
      studioLogo.onerror = () => {
        studioLogo.hidden = true;
        studioLogo.removeAttribute('src');
        if (headerBrand) headerBrand.classList.remove('brand-with-logo');
      };
      const categoryLabel = adminIsZh() ? (preset.labelZh || preset.label) : preset.label;
      $('studioMeta').textContent = t.slug
        ? `${t.slug} · ${categoryLabel} ${adminText('官网与品牌管理', 'website and brand console')}`
        : adminText('官网与品牌管理', 'Website and brand console');
      $('tenantSlug').value = t.slug || currentTenantSlug();
      updateSurfaceLinks();
      updateSurfaceHealth().catch((error) => console.warn('Surface health refresh failed.', error));
      renderPresetGrid(category);
      $('settingName').value = t.name || '';
      $('settingLogoUrl').value = t.logo_url || t.logoUrl || '';
      $('settingPlan').innerHTML = plans.map((p) => `<option value="${p.code}">${esc(p.name)} (${esc(p.code)})</option>`).join('');
      if (t.plan_code) $('settingPlan').value = t.plan_code;
      const currentPlan = plans.find((plan) => plan.code === t.plan_code) || {};
      const canExport = Boolean((currentPlan.features || {}).data_export);
      ['exportStudentsBtn', 'exportRegistrationsBtn', 'exportLedgerBtn'].forEach((id) => {
        const button = $(id);
        if (!button) return;
        button.disabled = !canExport;
        button.title = canExport ? '' : 'Data export is not included in the current plan.';
      });
      $('settingPrimaryColor').value = themeValue(visual, 'accent_color', t.primary_color || FALLBACK_THEME.accent_color);
      $('settingSecondaryColor').value = themeValue(visual, 'secondary_accent_color', t.secondary_color || FALLBACK_THEME.secondary_accent_color);
      $('settingCmsLayout').value = t.cms_layout || t.cmsLayout || 'bar';
      setToggle('settingShowWelcome', t.show_welcome, true);
      $('settingCategory').innerHTML = categoryOptions(category);
      /* Batch 5: localizedCopy is the bilingual source for studio identity; the
         flat field is what a tenant saved before it moved there. */
      $('settingSlogan').value = localized.slogan?.zh || t.slogan || preset.sloganZh || preset.slogan;
      $('settingSloganEn').value = localized.slogan?.en || t.slogan || preset.slogan;
      $('settingTimezone').value = t.timezone || 'Australia/Melbourne';
      $('settingPhone').value = t.contact_phone || t.contactPhone || '';
      $('settingEmail').value = t.contact_email || t.contactEmail || '';
      $('settingAddress').value = t.address || '';
      $('settingWelcome').value = localized.welcome_message?.zh || t.welcome_message || t.welcomeMessage || '';
      $('settingWelcomeEn').value = localized.welcome_message?.en || t.welcome_message || t.welcomeMessage || '';
      $('settingPortalLabel').value = t.copy_pack?.portal_label || t.copyPack?.portalLabel || preset.portalLabel;
      $('settingRegisterIntro').value = localized.registration_intro?.zh || preset.registerIntroZh || t.copy_pack?.register_intro || t.copyPack?.registerIntro || preset.registerIntro;
      $('settingRegisterIntroEn').value = localized.registration_intro?.en || t.copy_pack?.register_intro || t.copyPack?.registerIntro || preset.registerIntro;
      const profile = t.registration_profile || t.registrationProfile || defaultRegistrationProfile(category);
      const profileTitle = profile.title && typeof profile.title === 'object' ? profile.title : { zh: profile.title, en: profile.title };
      $('settingRegistrationTitle').value = localized.registration_title?.zh || preset.registrationTitleZh || profileTitle.zh || '学员报名';
      $('settingRegistrationTitleEn').value = localized.registration_title?.en || preset.registrationTitle || profileTitle.en || 'Quick Registration';
      fillRegistrationFields(profile);
      $('settingHeroEyebrow').value = hero.eyebrow || preset.label;
      $('settingHeroTitle').value = localized.hero_title?.zh || hero.title || t.name || '';
      $('settingHeroTitleEn').value = localized.hero_title?.en || hero.title || t.name || '';
      $('settingHeroSubtitle').value = localized.hero_subtitle?.zh || hero.subtitle || t.slogan || preset.slogan;
      $('settingHeroSubtitleEn').value = localized.hero_subtitle?.en || hero.subtitle || t.slogan || preset.slogan;
      $('settingHeroImageUrl').value = hero.hero_image_url || hero.heroImageUrl || '';
      $('settingPrimaryCta').value = localized.primary_cta?.zh || hero.primary_cta_label || hero.primaryCtaLabel || '预约体验';
      $('settingPrimaryCtaEn').value = localized.primary_cta?.en || hero.primary_cta_label || hero.primaryCtaLabel || 'Book a Trial';
      $('settingSecondaryCta').value = localized.secondary_cta?.zh || hero.secondary_cta_label || hero.secondaryCtaLabel || '查看课程';
      $('settingSecondaryCtaEn').value = localized.secondary_cta?.en || hero.secondary_cta_label || hero.secondaryCtaLabel || 'Explore Courses';
      $('settingSecondaryCtaTarget').value = hero.secondary_cta_target || hero.secondaryCtaTarget || 'auto';
      $('settingSecondaryCtaHref').value = hero.secondary_cta_href || hero.secondaryCtaHref || '';
      $('settingSecondaryCtaHrefGroup').hidden = $('settingSecondaryCtaTarget').value !== 'external';
      $('settingHeroStyle').value = hero.background_style || hero.backgroundStyle || 'soft';
      /* 'auto' 是新租户的默认，但存量记录里存着字面量 'organic' —— 那是当年
         写死的默认值，不是谁选的。两者都原样显示：这个下拉框该说的是租户
         存了什么，不是它今天恰好解析成什么。 */
      $('settingHeroShape').value = hero.hero_shape || hero.heroShape || 'auto';
      setToggle('settingShowStudentLogin', hero.show_student_login ?? hero.showStudentLogin, true);
      setToggle('settingShowPrincipal', website.show_principal ?? website.showPrincipal, true);
      setToggle('settingShowCourses', website.show_courses ?? website.showCourses, true);
      setToggle('settingShowGallery', website.show_gallery ?? website.showGallery, true);
      setToggle('settingShowFaq', website.show_faq ?? website.showFaq, true);
      setToggle('settingShowContact', website.show_contact ?? website.showContact, true);
      setToggle('settingShowStudentArea', website.show_student_area ?? website.showStudentArea, true);
      // Off by default: a studio that has written nothing about its space
      // should not publish an empty heading the first time it opens this tab.
      setToggle('settingShowAbout', website.show_about ?? website.showAbout, false);
      const aboutPair = (key, camel) => website[key] || website[camel] || {};
      const aboutEyebrow = aboutPair('about_eyebrow', 'aboutEyebrow');
      const aboutTitle = aboutPair('about_title', 'aboutTitle');
      const aboutBody = aboutPair('about_body', 'aboutBody');
      $('settingAboutEyebrow').value = aboutEyebrow.zh || '';
      $('settingAboutEyebrowEn').value = aboutEyebrow.en || '';
      $('settingAboutTitle').value = aboutTitle.zh || '';
      $('settingAboutTitleEn').value = aboutTitle.en || '';
      $('settingAboutBody').value = aboutBody.zh || '';
      $('settingAboutBodyEn').value = aboutBody.en || '';
      aboutImages = (website.about_images || website.aboutImages || [])
        .filter((url) => typeof url === 'string' && url).slice(0, ABOUT_IMAGE_LIMIT);
      aboutImageAlts = (website.about_image_alts || website.aboutImageAlts || [])
        .slice(0, aboutImages.length)
        .map((alt) => typeof alt === 'object' && alt ? { zh: alt.zh || alt.en || '', en: alt.en || alt.zh || '' } : { zh: String(alt || ''), en: String(alt || '') });
      while (aboutImageAlts.length < aboutImages.length) aboutImageAlts.push({ zh: '', en: '' });
      renderAboutImages();
      renderAboutItems(website.about_items || website.aboutItems);
      $('settingSeoTitle').value = website.seo_title || website.seoTitle || '';
      $('settingSeoDescription').value = website.seo_description || website.seoDescription || '';
      setToggle('settingShowShowcase', website.show_showcase ?? website.showShowcase, false);
      const showcaseLabel = aboutPair('showcase_label', 'showcaseLabel');
      const showcaseTitle = aboutPair('showcase_title', 'showcaseTitle');
      const showcaseLead = aboutPair('showcase_lead', 'showcaseLead');
      $('settingShowcaseLabel').value = showcaseLabel.zh || '';
      $('settingShowcaseLabelEn').value = showcaseLabel.en || '';
      $('settingShowcaseTitle').value = showcaseTitle.zh || '';
      $('settingShowcaseTitleEn').value = showcaseTitle.en || '';
      $('settingShowcaseLead').value = showcaseLead.zh || '';
      $('settingShowcaseLeadEn').value = showcaseLead.en || '';
      setToggle('settingShowTimetable', website.show_timetable ?? website.showTimetable, false);
      setToggle('settingShowTimetableBooking',
        website.show_timetable_booking ?? website.showTimetableBooking, false);
      $('settingTimetableWeeks').value =
        String(website.timetable_weeks ?? website.timetableWeeks ?? TIMETABLE_DEFAULT_WEEKS);
      const timetableLabel = aboutPair('timetable_label', 'timetableLabel');
      const timetableLead = aboutPair('timetable_lead', 'timetableLead');
      $('settingTimetableLabel').value = timetableLabel.zh || '';
      $('settingTimetableLabelEn').value = timetableLabel.en || '';
      $('settingTimetableLead').value = timetableLead.zh || '';
      $('settingTimetableLeadEn').value = timetableLead.en || '';
      /* A key the record does not carry takes the recommended default, not
         false. "Never mentioned" and "switched off" are different answers, and
         reading the first as the second would blank a studio's timetable the
         day this object gains a field. Mirrors the server's normalizer. */
      const storedFields = website.timetable_fields || website.timetableFields || {};
      Object.entries(TIMETABLE_FIELD_DEFAULTS).forEach(([key, fallback]) => {
        const camel = key.replace(/_([a-z])/g, (_m, c) => c.toUpperCase());
        const value = storedFields[key] ?? storedFields[camel] ?? fallback;
        setToggle(timetableFieldControl(key), value, false);
      });
      /* `currentTenantSlug()`, not `TENANT_SLUG`. The latter is the
         tenant-template convention (index/register/timetable are rendered per
         tenant and carry it as a literal); this console serves every tenant
         from one static file and reads the slug from the form.
         v8.10.0 shipped the wrong one, and because a ReferenceError aborts the
         rest of the function, everything below this line stopped running — the
         theme was never applied, so the contrast check measured unstyled
         defaults and reported 1.0:1. One undefined name, every symptom. */
      /* Only when a slug is actually known. With none, the markup's own
         `/<your studio>/timetable` stays — writing a placeholder from here
         would put an untranslated English word on a Chinese page. */
      const timetableSlug = currentTenantSlug();
      if (timetableSlug && $('timetableUrlHint')) {
        $('timetableUrlHint').textContent = `/${timetableSlug}/timetable`;
      }
      showcaseCategories = (website.showcase_categories || website.showcaseCategories || [])
        .slice(0, SHOWCASE_CATEGORY_LIMIT)
        .map((cat) => ({ id: cat.id || '', label: cat.label || { zh: '', en: '' } }));
      renderShowcaseCategories();
      // Everything the studio owns, not everything its plan publishes — the
      // editor is where a downgraded tenant can still see and reorder all of
      // its work.
      showcaseItems = (website.showcase_items || website.showcaseItems || [])
        .map((item) => ({
          image_url: item.image_url || item.imageUrl || '',
          category_id: item.category_id || item.categoryId || '',
          featured_rank: normalizeShowcaseFeaturedRank(
            item.featured_rank ?? item.featuredRank
          ),
          publication_state: normalizeShowcasePublicationState(
            item.publication_state || item.publicationState
          ),
          title: item.title || { zh: '', en: '' },
          caption: item.caption || { zh: '', en: '' },
          /* Rebuilt from the stored provider + id rather than kept as the
             original paste. The record holds what the server accepted, and
             showing the owner that is more honest than showing them what they
             typed — if their link was rewritten, they should see it. */
          video_url: showcaseWatchUrl(item.video_provider || item.videoProvider,
                                      item.video_id || item.videoId)
        }));
      renderShowcaseItems();
      const sectionLabel = (key, legacyValue, fallbackZh, fallbackEn) => {
        const pair = localized[key] || {};
        $(`setting${key.split('_').map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join('')}`).value = pair.zh || legacyValue || fallbackZh;
        $(`setting${key.split('_').map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join('')}En`).value = pair.en || legacyValue || fallbackEn;
      };
      sectionLabel('courses_label', website.courses_label || website.coursesLabel, '课程与班次', 'Courses & Classes');
      sectionLabel('gallery_label', website.gallery_label || website.galleryLabel, '学员%WORK%', 'Student %WORKS%');
      sectionLabel('faq_label', website.faq_label || website.faqLabel, '常见问题', 'Questions & Answers');
      sectionLabel('contact_label', website.contact_label || website.contactLabel, '联系我们', 'Contact');
      $('settingPrincipalName').value = principal.name || '';
      $('settingPrincipalTitle').value = localized.principal_title?.zh || principal.title || '创办人 / 主理人';
      $('settingPrincipalTitleEn').value = localized.principal_title?.en || principal.title || 'Founder & Principal';
      $('settingPrincipalBio').value = localized.principal_bio?.zh || principal.bio || '';
      $('settingPrincipalBioEn').value = localized.principal_bio?.en || principal.bio || '';
      $('settingPrincipalQuote').value = localized.principal_quote?.zh || principal.quote || '';
      $('settingPrincipalQuoteEn').value = localized.principal_quote?.en || principal.quote || '';
      $('settingPrincipalImageUrl').value = principal.image_url || principal.imageUrl || '';
      setVisualThemeFields(visual, themeValue(visual, 'style_id', preset.recommendedStyleId || ''));
      fillFaqItems(t.faq_items || t.faqItems || defaultFaqItems(category));
      fillMessageTemplates(t.message_templates || t.messageTemplates);
      updateThemePreview();
      setPublicationState('published');
      setSettingsDirty(false);
    }

    function settingsPayload() {
      // Resolve the scheme the operator actually selected: the default
      // visualTheme is the preset's *first* mode, which sent light-mode
      // status colours (and the wrong colorScheme) for dark drafts.
      const stylePreset = VISUAL_STYLE_PRESETS[activeVisualStyle];
      const styleTheme = (stylePreset?.schemes && stylePreset.schemes[activeColorScheme])
        || stylePreset?.visualTheme || defaultVisualTheme();
      const primary = $('settingPrimaryColor').value;
      const secondary = $('settingSecondaryColor').value;
      return {
        name: $('settingName').value.trim(),
        logoUrl: $('settingLogoUrl').value.trim(),
        planCode: $('settingPlan').value,
        primaryColor: primary,
        secondaryColor: secondary,
        cmsLayout: $('settingCmsLayout').value,
        showWelcome: toggleOn('settingShowWelcome'),
        category: $('settingCategory').value,
        slogan: $('settingSlogan').value.trim(),
        timezone: $('settingTimezone').value.trim(),
        contactPhone: $('settingPhone').value.trim(),
        contactEmail: $('settingEmail').value.trim(),
        address: $('settingAddress').value.trim(),
        welcomeMessage: $('settingWelcome').value.trim(),
        copyPack: {
          portalLabel: $('settingPortalLabel').value.trim(),
          registerIntro: $('settingRegisterIntro').value.trim()
        },
        localizedCopy: {
          heroTitle: { zh: $('settingHeroTitle').value.trim(), en: $('settingHeroTitleEn').value.trim() },
          heroSubtitle: { zh: $('settingHeroSubtitle').value.trim(), en: $('settingHeroSubtitleEn').value.trim() },
          primaryCta: { zh: $('settingPrimaryCta').value.trim(), en: $('settingPrimaryCtaEn').value.trim() },
          secondaryCta: { zh: $('settingSecondaryCta').value.trim(), en: $('settingSecondaryCtaEn').value.trim() },
          registrationTitle: { zh: $('settingRegistrationTitle').value.trim(), en: $('settingRegistrationTitleEn').value.trim() },
          registrationIntro: { zh: $('settingRegisterIntro').value.trim(), en: $('settingRegisterIntroEn').value.trim() },
          // Batch 5, class B. The flat `slogan` / `welcomeMessage` /
          // websiteProfile / principalProfile fields below still carry the
          // Chinese value, so nothing that reads them breaks.
          slogan: { zh: $('settingSlogan').value.trim(), en: $('settingSloganEn').value.trim() },
          welcomeMessage: { zh: $('settingWelcome').value.trim(), en: $('settingWelcomeEn').value.trim() },
          categoryLabel: { zh: industryPresetFor().labelZh || '', en: industryPresetFor().label || '' },
          principalTitle: { zh: $('settingPrincipalTitle').value.trim(), en: $('settingPrincipalTitleEn').value.trim() },
          principalBio: { zh: $('settingPrincipalBio').value.trim(), en: $('settingPrincipalBioEn').value.trim() },
          principalQuote: { zh: $('settingPrincipalQuote').value.trim(), en: $('settingPrincipalQuoteEn').value.trim() },
          coursesLabel: { zh: $('settingCoursesLabel').value.trim(), en: $('settingCoursesLabelEn').value.trim() },
          galleryLabel: { zh: $('settingGalleryLabel').value.trim(), en: $('settingGalleryLabelEn').value.trim() },
          faqLabel: { zh: $('settingFaqLabel').value.trim(), en: $('settingFaqLabelEn').value.trim() },
          contactLabel: { zh: $('settingContactLabel').value.trim(), en: $('settingContactLabelEn').value.trim() }
        },
        registrationProfile: collectRegistrationProfile(),
        heroProfile: {
          eyebrow: $('settingHeroEyebrow').value.trim(),
          title: $('settingHeroTitle').value.trim(),
          subtitle: $('settingHeroSubtitle').value.trim(),
          heroImageUrl: $('settingHeroImageUrl').value.trim(),
          primaryCtaLabel: $('settingPrimaryCta').value.trim(),
          secondaryCtaLabel: $('settingSecondaryCta').value.trim(),
          secondaryCtaTarget: $('settingSecondaryCtaTarget').value,
          secondaryCtaHref: $('settingSecondaryCtaHref').value.trim(),
          backgroundStyle: $('settingHeroStyle').value,
          heroShape: $('settingHeroShape').value,
          showStudentLogin: toggleOn('settingShowStudentLogin')
        },
        websiteProfile: {
          showPrincipal: toggleOn('settingShowPrincipal'),
          showCourses: toggleOn('settingShowCourses'),
          showGallery: toggleOn('settingShowGallery'),
          showFaq: toggleOn('settingShowFaq'),
          showContact: toggleOn('settingShowContact'),
          showStudentArea: toggleOn('settingShowStudentArea'),
          coursesLabel: $('settingCoursesLabelEn').value.trim() || $('settingCoursesLabel').value.trim(),
          galleryLabel: $('settingGalleryLabelEn').value.trim() || $('settingGalleryLabel').value.trim(),
          faqLabel: $('settingFaqLabelEn').value.trim() || $('settingFaqLabel').value.trim(),
          contactLabel: $('settingContactLabelEn').value.trim() || $('settingContactLabel').value.trim(),
          /* `_normalize_website_profile` rebuilds the profile from THIS object
             alone — it does not merge with what is stored. So every field the
             server keeps must be sent here, and until v8.5.4 seven were not:
             show_about, the three About text pairs, about_images, about_items
             and the two SEO overrides. Any save from this page silently
             erased all of them, which is why the About section had never
             appeared on a live site and why the flagship tenant's reclaimed
             <title> did not survive its first Save Draft. */
          showAbout: toggleOn('settingShowAbout'),
          aboutEyebrow: bilingualPair('settingAboutEyebrow', 'settingAboutEyebrowEn'),
          aboutTitle: bilingualPair('settingAboutTitle', 'settingAboutTitleEn'),
          aboutBody: bilingualPair('settingAboutBody', 'settingAboutBodyEn'),
          aboutImages: aboutImages.slice(0, ABOUT_IMAGE_LIMIT),
          aboutImageAlts: aboutImageAlts.slice(0, ABOUT_IMAGE_LIMIT).map((alt) => ({
            zh: (alt?.zh || alt?.en || '').trim(),
            en: (alt?.en || alt?.zh || '').trim(),
          })),
          aboutItems: collectAboutItems(),
          seoTitle: $('settingSeoTitle').value.trim(),
          seoDescription: $('settingSeoDescription').value.trim(),
          showShowcase: toggleOn('settingShowShowcase'),
          showcaseLabel: bilingualPair('settingShowcaseLabel', 'settingShowcaseLabelEn'),
          showcaseTitle: bilingualPair('settingShowcaseTitle', 'settingShowcaseTitleEn'),
          showcaseLead: bilingualPair('settingShowcaseLead', 'settingShowcaseLeadEn'),
          /* The ids go back up unchanged. They are generated server-side and
             never derived from the label, so dropping them here would mint new
             ones on every save and detach every work from its category. */
          showcaseCategories: showcaseCategories
            .filter((cat) => ((cat.label || {}).zh || '').trim() || ((cat.label || {}).en || '').trim())
            .slice(0, SHOWCASE_CATEGORY_LIMIT)
            .map((cat) => ({ id: cat.id || '', label: {
              zh: (cat.label.zh || cat.label.en || '').trim(),
              en: (cat.label.en || cat.label.zh || '').trim() } })),
          showcaseItems: collectShowcaseItems(),
          /* Same rule as the About block above: every key the server keeps
             must be sent, because `_normalize_website_profile` rebuilds from
             this object alone. A timetable field omitted here is a timetable
             field erased on the studio's next Save. */
          showTimetable: toggleOn('settingShowTimetable'),
          showTimetableBooking: toggleOn('settingShowTimetableBooking'),
          timetableWeeks: Number($('settingTimetableWeeks').value) || TIMETABLE_DEFAULT_WEEKS,
          timetableLabel: bilingualPair('settingTimetableLabel', 'settingTimetableLabelEn'),
          timetableLead: bilingualPair('settingTimetableLead', 'settingTimetableLeadEn'),
          timetableFields: Object.fromEntries(
            Object.keys(TIMETABLE_FIELD_DEFAULTS)
              .map((key) => [key, toggleOn(timetableFieldControl(key))]))
        },
        principalProfile: {
          show: toggleOn('settingShowPrincipal'),
          name: $('settingPrincipalName').value.trim(),
          title: $('settingPrincipalTitleEn').value.trim() || $('settingPrincipalTitle').value.trim(),
          bio: $('settingPrincipalBioEn').value.trim() || $('settingPrincipalBio').value.trim(),
          quote: $('settingPrincipalQuoteEn').value.trim() || $('settingPrincipalQuote').value.trim(),
          imageUrl: $('settingPrincipalImageUrl').value.trim()
        },
        faqItems: collectFaqItems(),
        messageTemplates: collectMessageTemplates(),
        visualTheme: {
          styleId: activeVisualStyle,
          /* The knob, as degrees. The picked hex is an input; the hue is the
             decision, and re-solving from it is what lets a solver improvement
             reach a studio that saved months ago. */
          accentHue: themeMode === 'custom' || activeAccentHue === null
            ? undefined : activeAccentHue,
          colorScheme: themeMode === 'custom'
            ? (luminance($('settingThemeBackground').value) < 0.18 ? 'dark' : 'light')
            : activeColorScheme,
          /* What the owner chose, which `colorScheme` cannot express: under
             `system` the site renders light OR dark per visitor, so the two
             fields answer different questions. A hand-mixed Advanced palette
             has only itself to publish, so it cannot follow anything. */
          schemePreference: themeMode === 'custom' ? undefined : activeSchemePreference,
          themeMode,
          backgroundColor: $('settingThemeBackground').value,
          panelColor: $('settingThemePanel').value,
          textColor: $('settingThemeText').value,
          mutedTextColor: $('settingThemeMuted').value,
          accentColor: primary,
          accentTextColor: readableText(primary),
          secondaryAccentColor: secondary,
          borderColor: $('settingThemeBorder').value,
          successColor: themeValue(styleTheme, 'success_color', FALLBACK_THEME.success_color),
          warningColor: themeValue(styleTheme, 'warning_color', FALLBACK_THEME.warning_color),
          dangerColor: themeValue(styleTheme, 'danger_color', FALLBACK_THEME.danger_color),
          buttonStyle: $('settingButtonStyle').value,
          fontMood: $('settingFontMood').value
        }
      };
    }

    async function verifyPublicBrandPublished(_expectedPayload, expectedVersion = publishedVersionLabel) {
      const slug = currentTenantSlug();
      if (!expectedVersion) {
        const error = new Error('Published version is not available yet.');
        error.code = 'PUBLIC_VERSION_PENDING';
        throw error;
      }
      let status;
      try {
        status = await api(`/tenant/brand/publication-status/${encodeURIComponent(expectedVersion)}`, {
          credentials: 'same-origin',
          cache: 'no-store',
        });
      } catch (cause) {
        const error = new Error('Publication status could not be checked.');
        error.code = 'PUBLIC_STATUS_UNAVAILABLE';
        error.cause = cause;
        throw error;
      }
      if (status.state === 'attention') {
        const error = new Error('The saved publication needs attention.');
        error.code = 'PUBLIC_PUBLICATION_INVALID';
        error.details = { checks: status.checks || [] };
        throw error;
      }
      if (status.state !== 'ready' || Number(status.publishedVersion || 0) < Number(expectedVersion)) {
        const error = new Error('Published content is saved; public pages are still confirming the new version.');
        error.code = 'PUBLIC_VERSION_PENDING';
        error.details = {
          expectedVersion,
          actualVersion: status.publishedVersion || null,
          checks: status.checks || [],
        };
        throw error;
      }

      let surfaceContract;
      try {
        surfaceContract = await window.StudioSaaS.publicSurface.fetch(
          `/v1/public/${encodeURIComponent(slug)}`,
          { credentials: 'same-origin', cache: 'no-store' },
        );
      } catch (cause) {
        const error = new Error('Published content is saved; the public navigation is still confirming.');
        error.code = 'PUBLIC_SURFACE_UNAVAILABLE';
        error.cause = cause;
        throw error;
      }
      if (Number(surfaceContract.publishedVersion || 0) < Number(expectedVersion)) {
        const error = new Error('Published content is saved; the public navigation is still confirming.');
        error.code = 'PUBLIC_VERSION_PENDING';
        error.details = {
          expectedVersion,
          actualVersion: surfaceContract.publishedVersion || null,
          surface: 'surface',
        };
        throw error;
      }

      const checks = [{ path: 'surface', ok: true }];
      const website = _expectedPayload?.websiteProfile || {};
      const registerResponse = await fetch(`/${encodeURIComponent(slug)}/register`, {
        credentials: 'same-origin',
        cache: 'no-store',
      });
      checks.push({ path: 'register', ok: registerResponse.ok });
      if (website.showShowcase) {
        const showcaseResponse = await fetch(
          `/v1/public/${encodeURIComponent(slug)}/showcase?surface=home&offset=0`,
          { credentials: 'same-origin', cache: 'no-store' },
        );
        const showcase = await showcaseResponse.json().catch(() => ({}));
        checks.push({ path: 'showcase', ok: showcaseResponse.ok && (showcase.enabled === false || Number(showcase.total || 0) >= 0) });
      }
      if (website.showTimetable) {
        const timetableResponse = await fetch(
          `/v1/public/${encodeURIComponent(slug)}/timetable`,
          { credentials: 'same-origin', cache: 'no-store' },
        );
        const timetable = await timetableResponse.json().catch(() => ({}));
        checks.push({ path: 'timetable', ok: timetableResponse.ok && (timetable.enabled === false || Array.isArray(timetable.days)) });
      }
      const failed = checks.filter((check) => !check.ok).map((check) => check.path);
      if (failed.length) {
        const error = new Error('Published content is saved; one public page is still confirming.');
        error.code = 'PUBLIC_SURFACE_UNAVAILABLE';
        error.details = { surfaces: failed };
        throw error;
      }
      publishedSurfaceContract = surfaceContract;
      return {
        contract: surfaceContract,
        checked: checks.map((check) => check.path),
        verifiedAt: new Date().toISOString(),
      };
    }


    function validatePublishPayload(payload) {
      if (!payload.name) throw new Error('Studio name is required.');
      if (payload.heroProfile.secondaryCtaTarget === 'external' && !payload.heroProfile.secondaryCtaHref) {
        const error = new Error('Add an external destination URL or choose another secondary CTA destination.');
        error.code = 'FIELD_VALIDATION';
        error.details = { tab: 'hero', field: 'settingSecondaryCtaHref' };
        throw error;
      }
      const placeholderPattern = /placeholder|principal name|主理人姓名|占位文案/i;
      const pairText = (value) => (value && typeof value === 'object' ? String(value.zh || value.en || '') : String(value || ''));
      const requiredPublicCopy = [
        ['Hero title', payload.heroProfile.title],
        ['Registration title', pairText(payload.registrationProfile.title)],
        ['Registration introduction', payload.copyPack.registerIntro]
      ];
      /* The copy a family must see before they can enquire. The class-B identity
         pairs added in batch 5 (welcome band, principal bio and quote) are
         deliberately optional — the portal hides those sections when they are
         blank, so requiring them here would block publishing for a studio that
         simply has no principal photo yet. A pair that is filled in one language
         only is not an error either: the API mirrors it into the other. */
      const requiredBilingualKeys = [
        'heroTitle', 'hero_title', 'heroSubtitle', 'hero_subtitle',
        'primaryCta', 'primary_cta', 'secondaryCta', 'secondary_cta',
        'registrationTitle', 'registration_title', 'registrationIntro', 'registration_intro'
      ];
      Object.entries(payload.localizedCopy || {}).forEach(([key, pair]) => {
        if (!requiredBilingualKeys.includes(key)) return;
        const zh = String(pair?.zh || '').trim();
        const en = String(pair?.en || '').trim();
        if (!zh && !en) requiredPublicCopy.push([`${key} in Chinese or English`, '']);
      });
      const missing = requiredPublicCopy.filter(([, value]) => !value || placeholderPattern.test(value)).map(([label]) => label);
      if (!payload.contactPhone && !payload.contactEmail) missing.push('Phone or email');
      if (payload.websiteProfile.showPrincipal && (!payload.principalProfile.name || placeholderPattern.test(payload.principalProfile.name))) {
        missing.push('Principal or teaching team name');
      }
      if (missing.length) throw new Error(`Complete public content before publishing: ${missing.join(', ')}.`);
      const theme = payload.visualTheme || {};
      const contrastChecks = [
        ['Body text on page', theme.textColor, theme.backgroundColor],
        ['Body text on panels', theme.textColor, theme.panelColor],
        ['Muted text on page', theme.mutedTextColor, theme.backgroundColor],
        ['Muted text on panels', theme.mutedTextColor, theme.panelColor],
        ['Primary button text', theme.accentTextColor, theme.accentColor],
      ];
      const failures = contrastChecks
        .map(([label, foreground, background]) => [label, contrastRatio(foreground, background)])
        .filter(([, ratio]) => ratio < 4.5);
      if (failures.length) {
        throw new Error(`Improve colour contrast before publishing: ${failures.map(([label, ratio]) => `${label} ${ratio.toFixed(1)}:1`).join(', ')}. Minimum is 4.5:1.`);
      }
    }

    async function saveDraft() {
      validateBrandFields();
      const payload = settingsPayload();
      await api('/tenant/brand-draft', { method: 'PUT', body: JSON.stringify(payload) });
      setPublicationState('draft');
      setSettingsDirty(false);
      showToast('Draft saved. Public pages have not changed.');
      showPublishError('');
    }

    function publishVerificationMessage(error) {
      const code = error?.code || 'SURFACE_UNAVAILABLE';
      const messages = {
        PUBLIC_PROJECTION_MISMATCH: ['已成功保存，但检测到公开投影异常；数据安全保留，请检查公开页面。', 'Saved successfully, but the public projection needs attention. Your data is safe; check the public page.'],
        SURFACE_UNAVAILABLE: ['已成功发布，公开页面确认中；数据安全保留，可稍后重新检查。', 'Published successfully; public pages are still confirming. Your data is safe; try again shortly.'],
        PUBLIC_SURFACE_UNAVAILABLE: ['已成功发布，公开导航仍在确认中；可稍后重新检查。', 'Published successfully; public navigation is still confirming. Try again shortly.'],
        PUBLIC_SURFACE_INVALID_RESPONSE: ['已成功发布，公开接口返回格式异常；可稍后重新检查。', 'Published successfully, but the public endpoint returned an invalid response. Try again shortly.'],
        PUBLIC_STATUS_UNAVAILABLE: ['已成功发布，发布状态暂时无法确认；可稍后重新检查。', 'Published successfully, but publication status could not be checked. Try again shortly.'],
        PUBLIC_PUBLICATION_INVALID: ['发布记录需要处理，请联系管理员检查发布版本。', 'The publication record needs attention. Ask an administrator to check the published version.'],
        PUBLIC_VERSION_PENDING: ['已成功发布，公开页面正在确认新版本。', 'Published successfully; public pages are confirming the new version.'],
        NETWORK_RETRY: ['已成功发布，公开页面确认中；可稍后重新检查。', 'Published successfully; public pages are still confirming. Try again shortly.'],
      };
      const pair = messages[code] || messages.SURFACE_UNAVAILABLE;
      return adminText(pair[0], pair[1]);
    }

    function showPublishError(message, error = null) {
      const box = $('publishErrorSummary');
      if (!box) return;
      if (!message) {
        box.textContent = '';
        delete box.dataset.tone;
        box.classList.add('hidden');
        return;
      }
      const field = error?.details?.field || '';
      const targetTab = error?.details?.tab || '';
      const warningCodes = new Set([
        'PUBLIC_VERSION_PENDING', 'PUBLIC_STATUS_UNAVAILABLE', 'PUBLIC_SURFACE_UNAVAILABLE',
        'SURFACE_UNAVAILABLE', 'NETWORK_RETRY',
      ]);
      box.dataset.tone = warningCodes.has(error?.code) ? 'warning' : 'danger';
      const details = error?.details && typeof error.details === 'object'
        ? Object.entries(error.details)
          .filter(([key]) => !['field', 'tab'].includes(key))
          .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.map((item) => typeof item === 'object' ? (item.key || item.path || item.state || JSON.stringify(item)) : item).join(', ') : value}`)
          .join(' · ')
        : '';
      box.replaceChildren();
      const copy = document.createElement('span');
      copy.textContent = `${message}${details ? ` ${details}` : ''}`;
      box.appendChild(copy);
      if (field && targetTab) {
        const jump = document.createElement('button');
        jump.type = 'button';
        jump.className = 'btn-secondary btn-sm';
        jump.textContent = localiseAdminText('Go to field');
        jump.addEventListener('click', () => {
          switchWorkbenchTab(targetTab);
          const control = document.getElementById(field);
          if (control) control.focus();
        });
        box.appendChild(jump);
      }
      box.classList.remove('hidden');
      switchWorkbenchTab('advanced');
      box.focus();
    }

    async function retryPublishVerification() {
      if (!lastPublishedPayload) return;
      const button = $('retryPublishVerificationBtn');
      if (button) { button.disabled = true; button.textContent = localiseAdminText('Checking...'); }
      try {
        await verifyPublicBrandPublished(lastPublishedPayload, publishedVersionLabel);
        lastPublicationError = null;
        setPublicationState('published', publishedVersionLabel);
        setSettingsDirty(false);
        showToast(localiseAdminText('Public pages verified'));
        showPublishError('');
        await updateSurfaceHealth();
      } catch (error) {
        lastPublicationError = error;
        setPublicationState('pending', publishedVersionLabel);
        setSettingsDirty(false);
        showToast(publishVerificationMessage(error), 'warning');
        showPublishError(publishVerificationMessage(error), error);
      } finally {
        if (button) { button.disabled = false; button.textContent = localiseAdminText('Recheck public pages'); }
      }
    }

    async function publishSettings() {
      try {
        validateBrandFields();
        const payload = settingsPayload();
        validatePublishPayload(payload);
        await api('/tenant/brand-draft', { method: 'PUT', body: JSON.stringify(payload) });
        const data = await api('/tenant', { method: 'PATCH', body: JSON.stringify(payload) });
        lastPublishedPayload = payload;
        lastPublicationError = null;
        tenant = data.tenant || tenant;
        publishedBaselinePayload = JSON.parse(JSON.stringify(payload));
        fillSettings();
        setPublicationState('published', data.publishedVersion || '');
        setSettingsDirty(false);
        try {
          await verifyPublicBrandPublished(payload, data.publishedVersion || '');
          await updateSurfaceHealth();
          await loadBrandWorkspace();
          showToast(localiseAdminText('Public pages verified'));
          showPublishError('');
        } catch (err) {
          lastPublicationError = err;
          /* The write has already committed. Keep the editor clean and mark
             verification as pending so the owner never re-saves over a good
             publication just because a projection was briefly stale. */
          setPublicationState('pending', data.publishedVersion || '');
          setSettingsDirty(false);
          await updateSurfaceHealth().catch((error) => console.warn('Surface health refresh failed.', error));
          showToast(publishVerificationMessage(err), 'warning');
          showPublishError(publishVerificationMessage(err), err);
        }
      } catch (err) {
        setPublicationState('error');
        setSettingsDirty(true);
        showPublishError(err.message || 'Publish failed.', err);
        throw err;
      }
    }

    function applyDraftToEditor(payload) {
      if (!payload || typeof payload !== 'object') return;
      tenant = {
        ...tenant,
        ...payload,
        primary_color: payload.primaryColor || tenant.primary_color,
        secondary_color: payload.secondaryColor || tenant.secondary_color,
        contact_phone: payload.contactPhone ?? tenant.contact_phone,
        contact_email: payload.contactEmail ?? tenant.contact_email,
        welcome_message: payload.welcomeMessage ?? tenant.welcome_message,
        logo_url: payload.logoUrl ?? tenant.logo_url,
        cms_layout: payload.cmsLayout ?? tenant.cms_layout,
        show_welcome: payload.showWelcome ?? tenant.show_welcome,
        copy_pack: payload.copyPack ?? tenant.copy_pack,
        localized_copy: payload.localizedCopy ?? tenant.localized_copy,
        registration_profile: payload.registrationProfile ?? tenant.registration_profile,
        hero_profile: payload.heroProfile ?? tenant.hero_profile,
        website_profile: payload.websiteProfile ?? tenant.website_profile,
        principal_profile: payload.principalProfile ?? tenant.principal_profile,
        faq_items: payload.faqItems ?? tenant.faq_items,
        message_templates: payload.messageTemplates ?? tenant.message_templates,
        visual_theme: payload.visualTheme ?? tenant.visual_theme
      };
      fillSettings();
      setPublicationState('draft');
      setSettingsDirty(false);
    }

    function renderBrandVersions() {
      const list = $('brandVersionList');
      list.replaceChildren();
      if (!brandVersions.length) {
        list.className = 'empty-state';
        list.textContent = 'No published versions yet.';
        return;
      }
      list.className = '';
      brandVersions.forEach((version) => {
        const row = document.createElement('div');
        row.className = 'summary-item';
        const detail = document.createElement('div');
        const title = document.createElement('strong');
        title.textContent = `Version ${version.version_number}`;
        const meta = document.createElement('div');
        meta.className = 'text-muted';
        meta.textContent = `${new Date(version.published_at).toLocaleString()} · ${version.published_by || 'Studio owner'}`;
        detail.append(title, meta);
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'btn-secondary btn-sm';
        button.textContent = 'Restore to Draft';
        button.addEventListener('click', () => restoreBrandVersion(version.id));
        row.append(detail, button);
        list.appendChild(row);
      });
    }

    async function loadBrandWorkspace() {
      const data = await api('/tenant/brand-workspace');
      brandVersions = data.versions || [];
      currentShowcaseLimit = Number(data.limits?.showcase) || 0;
      renderBrandVersions();
      renderShowcasePublishNotice();
      await loadPublishedSurfaceContract();
      return data;
    }

    async function loadPublishedSurfaceContract() {
      const slug = currentTenantSlug();
      if (!slug || !window.StudioSaaS.publicSurface) {
        publishedSurfaceContract = null;
        return null;
      }
      try {
        publishedSurfaceContract = await window.StudioSaaS.publicSurface.fetch(
          `/v1/public/${encodeURIComponent(slug)}`,
          { credentials: 'same-origin' },
        );
        return publishedSurfaceContract;
      } catch (error) {
        publishedSurfaceContract = null;
        error.code = error.code || 'PUBLIC_SURFACE_UNAVAILABLE';
        throw error;
      } finally {
        updateThemePreview();
      }
    }

    async function restoreBrandVersion(versionId) {
      /* U2: the click handler has no .catch, so a failed restore was silent —
         the owner kept editing the old draft believing the restore happened. */
      try {
        const data = await api(`/tenant/brand-versions/${encodeURIComponent(versionId)}/restore`, { method: 'POST', body: '{}' });
        applyDraftToEditor(data.draft || {});
        showToast('Previous version restored to draft. Review it before publishing.');
      } catch (err) {
        showToast(`Restore failed: ${err.message}`, 'error');
      }
    }

    async function uploadLogo() {
      const file = $('settingLogoFile').files[0];
      if (!file) return;
      const formData = new FormData();
      formData.append('file', file);
      const data = await api('/tenant/logo', { method: 'POST', body: formData });
      $('settingLogoUrl').value = data.url || '';
      setSettingsDirty(true);
      updateThemePreview();
      showToast('Logo uploaded. Save Draft or Publish when you are ready.');
    }

    async function uploadWebsiteImage(target, inputId, urlInputId) {
      const file = $(inputId).files[0];
      if (!file) return;
      const formData = new FormData();
      formData.append('target', target);
      formData.append('file', file);
      const data = await api('/tenant/website-media', { method: 'POST', body: formData });
      $(urlInputId).value = data.url || '';
      /* Uploading a hero photo is a request to SHOW a hero photo.
         This filled the URL field and stopped, while Hero Style three fields
         below still said "Soft Art Board" — and the public page only adds
         body.hero-image when the style is `image`, so `.hero-art img` stayed
         display:none. Upload succeeded, Save succeeded, Publish succeeded, and
         the photo was never on the site. Measured on production: all six
         tenants had an empty hero_image_url, which is what that dead end
         produces.
         The owner can still choose the art board afterwards; what they cannot
         do any more is choose it by accident. */
      let switched = false;
      if (target === 'hero' && data.url && $('settingHeroStyle')?.value !== 'image') {
        $('settingHeroStyle').value = 'image';
        switched = true;
      }
      setSettingsDirty(true);
      updateThemePreview();
      const noun = target === 'hero' ? 'Hero' : 'Principal';
      showToast(switched
        ? `${noun} image uploaded and Hero Style set to Photo panel. Save Draft or Publish when ready.`
        : `${noun} image uploaded. Save Draft or Publish when ready.`);
    }

    /* Appends rather than replaces: the About carousel is a set of photos, not
       one slot. Its own function for that reason — uploadWebsiteImage writes
       into a single URL field. */
    async function uploadAboutImage() {
      const picker = $('settingAboutImageFile');
      const file = picker.files[0];
      if (!file) return;
      if (aboutImages.length >= ABOUT_IMAGE_LIMIT) {
        picker.value = '';
        showToast(`About photos are limited to ${ABOUT_IMAGE_LIMIT}. Remove one first.`);
        return;
      }
      const formData = new FormData();
      formData.append('target', 'about');
      formData.append('file', file);
      const data = await api('/tenant/website-media', { method: 'POST', body: formData });
      // Cleared either way, so a failed upload does not leave a filename in
      // the control implying it was accepted.
      picker.value = '';
      if (!data.url) return;
      aboutImages.push(data.url);
      aboutImageAlts.push({ zh: '', en: '' });
      renderAboutImages();
      setSettingsDirty(true);
      /* Uploading a photo of the space is a request to SHOW the space —
         the same reasoning as the hero photo above, and the same dead end
         avoided: the section stays hidden until show_about is on. */
      let switched = false;
      if (!toggleOn('settingShowAbout')) {
        setToggle('settingShowAbout', true, true);
        switched = true;
      }
      showToast(switched
        ? 'About photo uploaded and the About section switched on. Save Draft or Publish when ready.'
        : 'About photo uploaded. Save Draft or Publish when ready.');
    }

    async function loadAnalytics() {
      const days = Number($('analyticsDays').value || 30);
      const data = await api(`/tenant/analytics?days=${encodeURIComponent(days)}`);
      const summary = data.summary || {};
      $('analyticsPageViews').textContent = Number(summary.page_views || 0).toLocaleString();
      $('analyticsSessions').textContent = Number(summary.anonymous_sessions || 0).toLocaleString();
      $('analyticsCtaClicks').textContent = Number(summary.cta_clicks || 0).toLocaleString();
      $('analyticsRegistrations').textContent = Number(summary.registration_submitted || 0).toLocaleString();
      const box = $('analyticsCampaigns');
      const rows = data.campaigns || [];
      if (!rows.length) {
        box.className = 'empty-state';
        box.textContent = 'No public portal events in this period.';
        return;
      }
      box.className = '';
      box.innerHTML = rows.map((row) => `
        <div class="info-row"><span class="k">${esc(row.campaign || '(direct)')}</span><span class="v">${Number(row.page_views || 0)} views · ${Number(row.registrations || 0)} registrations</span></div>
      `).join('');
    }

    /* Owner audit trail. Same date convention as the publication history
       (new Date(...).toLocaleString()), rows built with textContent so no
       server-provided string reaches innerHTML. */
    function formatAuditTime(iso) {
      const date = new Date(iso);
      return Number.isNaN(date.getTime()) ? text(iso) : date.toLocaleString();
    }

    async function loadAuditLogs() {
      const body = $('auditLogBody');
      const emptyBox = $('auditLogEmpty');
      if (!body || !emptyBox) return;
      const action = $('auditActionFilter').value.trim();
      emptyBox.hidden = false;
      emptyBox.textContent = 'Loading audit records…';
      try {
        const query = action ? `&action=${encodeURIComponent(action)}` : '';
        const data = await api(`/audit-logs?limit=50${query}`);
        const rows = data.auditLogs || [];
        body.replaceChildren();
        if (!rows.length) {
          emptyBox.textContent = 'No audit records yet.';
          return;
        }
        emptyBox.hidden = true;
        rows.forEach((row) => {
          const tr = document.createElement('tr');
          const time = document.createElement('td');
          time.className = 'audit-time';
          time.textContent = formatAuditTime(row.createdAt);
          const actor = document.createElement('td');
          actor.textContent = text(row.actorEmail);
          const actionCell = document.createElement('td');
          actionCell.className = 'audit-action';
          actionCell.textContent = text(row.action);
          if (row.metadata && Object.keys(row.metadata).length) {
            actionCell.title = JSON.stringify(row.metadata);
          }
          const resource = document.createElement('td');
          resource.className = 'audit-resource';
          resource.textContent = [row.resourceType, row.resourceId].filter(Boolean).join(' · ') || '-';
          tr.append(time, actor, actionCell, resource);
          body.appendChild(tr);
        });
      } catch (err) {
        body.replaceChildren();
        emptyBox.hidden = false;
        emptyBox.textContent = `Failed to load audit records: ${err.message}`;
      }
    }

    function applyVisualStyle(styleId, { remember = true, scheme = null } = {}) {
      const style = VISUAL_STYLE_PRESETS[styleId];
      if (!style) return;
      const isZh = window.AdminI18n?.language === 'zh';
      const declaredModes = Array.isArray(style.modes) && style.modes.length ? style.modes : [];
      const modes = declaredModes.length
        ? declaredModes
        : (style.schemes && Object.keys(style.schemes).length ? Object.keys(style.schemes) : ['light', 'dark']);
      const name = styleName(style);
      // Keep the operator's current appearance if the new style offers it.
      const nextScheme = scheme && modes.includes(scheme) ? scheme
                       : (modes.includes(activeColorScheme) ? activeColorScheme : modes[0]);
      activeColorScheme = nextScheme;
      // A single-mode style cannot follow the visitor; drop back to what it has.
      if (activeSchemePreference === 'system' && modes.length < 2) activeSchemePreference = nextScheme;
      else if (activeSchemePreference !== 'system') activeSchemePreference = nextScheme;
      if (remember) rememberPresetState(isZh ? `已将${name}应用到当前草稿。` : `${name} applied to this draft.`);
      setVisualThemeFields((style.schemes && style.schemes[nextScheme]) || style.visualTheme || {}, styleId);
      themeMode = 'preset';
      renderThemeGrid();
      renderStylePresetGrid();
      setSettingsDirty(true);
      updateThemePreview();
      /* Custom carries no palette of its own — it is the picker. Re-solve at
         whatever hue is already stored so selecting the card shows a real
         result rather than the literal placeholder in the presets file. A null
         hue means "never set"; the endpoint supplies the starting hue rather
         than this page carrying a second copy of it. */
      if (styleId === FREE_ACCENT_STYLE_ID) previewAccentHue(activeAccentHue);
      showToast(isZh ? `已应用${name}；发布前不会影响公开页面。` : `${name} style applied. Nothing is public until you publish.`);
    }

    function applyCategoryPreset({ remember = true } = {}) {
      const preset = INDUSTRY_PRESETS[$('settingCategory').value] || INDUSTRY_PRESETS.general;
      const isZh = window.AdminI18n?.language === 'zh';
      if (remember) rememberPresetState(isZh ? `已将${industryName(preset)}行业预设应用到当前草稿。` : `${industryName(preset)} industry preset applied to this draft.`);
      renderPresetGrid($('settingCategory').value);
      $('settingSlogan').value = preset.sloganZh || preset.slogan;
      $('settingSloganEn').value = preset.slogan;
      $('settingPortalLabel').value = preset.portalLabel;
      $('settingRegisterIntro').value = preset.registerIntroZh || preset.registerIntro;
      $('settingRegisterIntroEn').value = preset.registerIntro;
      $('settingHeroEyebrow').value = preset.label;
      $('settingHeroTitle').value = preset.localizedCopy?.hero_title?.zh || $('settingName').value || preset.labelZh || preset.label;
      $('settingHeroTitleEn').value = preset.localizedCopy?.hero_title?.en || $('settingName').value || preset.label;
      $('settingHeroSubtitle').value = preset.localizedCopy?.hero_subtitle?.zh || preset.sloganZh || preset.slogan;
      $('settingHeroSubtitleEn').value = preset.localizedCopy?.hero_subtitle?.en || preset.slogan;
      $('settingPrimaryCta').value = preset.localizedCopy?.primary_cta?.zh || '预约体验';
      $('settingPrimaryCtaEn').value = preset.localizedCopy?.primary_cta?.en || 'Book a Trial';
      $('settingSecondaryCta').value = preset.localizedCopy?.secondary_cta?.zh || '查看课程';
      $('settingSecondaryCtaEn').value = preset.localizedCopy?.secondary_cta?.en || 'Explore Programs';
      const profile = defaultRegistrationProfile($('settingCategory').value);
      $('settingRegistrationTitle').value = preset.registrationTitleZh || profile.title?.zh || profile.title || '';
      $('settingRegistrationTitleEn').value = preset.registrationTitle || profile.title?.en || profile.title || '';
      fillRegistrationFields(profile);
      /* The industry writes COPY, FORMS and the operating template — never a
         palette. It used to call setVisualThemeFields() with its recommended
         theme right here, which is how clicking an industry card silently
         repainted a studio that had already chosen its own colours. The
         recommendation survives as a badge in the theme grid (see
         renderThemeGrid), which is the honest form of "recommended". */
      fillFaqItems(defaultFaqItems($('settingCategory').value));
      renderThemeGrid();
      setSettingsDirty(true);
      updateThemePreview();
      showToast(isZh ? `已应用${industryName(preset)}行业的文案与报名问题；配色未改动。` : `${industryName(preset)} copy and registration questions applied. Your colours are unchanged.`);
    }

    function setLoadingState(loading) {
      $('refreshBtn').disabled = loading;
      $('refreshIcon').textContent = loading ? '...' : '↻';
    }

    /* Tenant data failed to load. Rendering the editable DEFAULT form here
       was the defect: Save Draft / Publish stayed clickable over placeholder
       values, and one click would overwrite the real tenant. The editor is
       replaced by a blocking state until a retry succeeds. */
    let loadBlocked = false;
    function setLoadBlockedState(err) {
      loadBlocked = true;
      $('adminContent').classList.add('hidden');
      $('loadErrorPanel').classList.remove('hidden');
      const blockedTitle = adminText('工作室数据载入失败',
        'Studio data could not be loaded');
      $('loadErrorTitle').textContent = blockedTitle;
      $('loadErrorMessage').textContent = adminText(
        `编辑区已锁定，避免用默认值覆盖线上内容。错误：${err.message}`,
        `Editing is locked so default values cannot overwrite the live studio. Error: ${err.message}`);
      const needsSupport = Boolean(err && err.needsSupportSession);
      $('loadErrorSupportHint').textContent = needsSupport
        ? adminText('这家工作室需要支持会话：请先在 Super Admin（平台控制台）开启支持会话，再回来重试。',
                    'This studio requires a support session: start one from Super Admin (platform console), then retry here.')
        : adminText('如果你是平台操作员且需要支持会话，请先在 Super Admin 开启，再重试。',
                    'If you are a platform operator and a support session is required, start one from Super Admin first, then retry.');
      $('loadErrorSupportLink').classList.toggle('hidden', !needsSupport);
      $('loadErrorRetryBtn').textContent = adminText('重试', 'Retry');
      const supportLinkLabel = adminText('打开 Super Admin',
        'Open Super Admin');
      $('loadErrorSupportLink').textContent = supportLinkLabel;
    }

    function clearLoadBlockedState() {
      loadBlocked = false;
      $('loadErrorPanel').classList.add('hidden');
      if (currentUser) $('adminContent').classList.remove('hidden');
    }

    async function refresh() {
      if (!currentUser) return;
      localStorage.setItem('studiosaas_tenant_slug', currentTenantSlug());
      setLoadingState(true);
      try {
        const [tenantData, planData, workspaceData] = await Promise.all([
          api('/tenant'), authApi('/plans'), api('/tenant/brand-workspace')
        ]);
        clearLoadBlockedState();
        tenant = tenantData.tenant || tenantData.settings || {};
        plans = planData.plans || [];
        currentShowcaseLimit = Number(workspaceData.limits?.showcase) || 0;
        fillSettings();
        publishedBaselinePayload = JSON.parse(JSON.stringify(settingsPayload()));
        brandVersions = workspaceData.versions || [];
        renderBrandVersions();
        if (workspaceData.draft?.payload) applyDraftToEditor(workspaceData.draft.payload);
        renderPublishChanges();
        try {
          await loadPublishedSurfaceContract();
        } catch (surfaceError) {
          showToast(publishVerificationMessage(surfaceError), 'warning');
        }
        switchWorkbenchTab(requestedWorkbenchTab(), {syncUrl: false});
      } catch (err) {
        if (err.status === 401) {
          clearLoadBlockedState();
          setAuthState(null);
        } else {
          /* Any other failure blocks the editor instead of leaving a
             default form with live Save/Publish buttons behind a toast. */
          setLoadBlockedState(err);
        }
        showToast(`Failed to load Studio Admin: ${err.message}`, 'error');
      } finally {
        setLoadingState(false);
      }
    }

    function bindEvents() {
      /* Root /studio-admin is a neutral tenant login. It never recovers a
         previous tenant from localStorage or silently picks a demo. A
         tenant-specific route locks its own slug; the root requires an
         explicit operator choice. */
      const routeSlug = pathTenantSlug();
      $('tenantSlug').value = routeSlug;
      $('tenantSlug').readOnly = Boolean(routeSlug);
      if (!currentTenantSlug()) {
        showToast('Enter the studio URL slug to continue.', 'error');
      }
      $('loginForm').addEventListener('submit', loginStudioAdmin);
      $('logoutBtn').addEventListener('click', logoutStudioAdmin);
      $('changePasswordBtn').addEventListener('click', openChangePasswordModal);
      $('refreshBtn').addEventListener('click', refresh);
      /* The blocked state offers the one action that can resolve it. A retry
         that fails again simply re-renders the same blocked panel. */
      $('loadErrorRetryBtn').addEventListener('click', () => { checkSession(); });
      $('tenantSlug').addEventListener('change', () => {
        localStorage.setItem('studiosaas_tenant_slug', currentTenantSlug());
        updateSurfaceLinks();
        updateSurfaceHealth().catch((error) => console.warn('Surface health refresh failed.', error));
        checkSession();
      });
      /* The account menu is a <details>, so opening and closing is the
         browser's job. These two only add what a disclosure does not give
         for free: Escape closes it, and so does a click outside it. */
      const headerMenu = $('headerMenu');
      document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && headerMenu.open) {
          headerMenu.open = false;
          headerMenu.querySelector('summary').focus();
        }
      });
      document.addEventListener('click', (event) => {
        if (headerMenu.open && !headerMenu.contains(event.target)) headerMenu.open = false;
      });
      /* One switch lives in one place; the tabs that describe a module link to
         it rather than growing a second control for the same setting. */
      document.querySelectorAll('[data-goto-switch]').forEach((button) => {
        button.addEventListener('click', () => {
          switchWorkbenchTab('website');
          const target = $(button.dataset.gotoSwitch);
          if (!target) return;
          target.focus({ preventScroll: false });
          target.closest('.switch-row')?.scrollIntoView({ block: 'center', behavior: 'smooth' });
        });
      });
      $('saveDraftBtn').addEventListener('click', () => runUiAction('saveDraftBtn', 'Saving Draft...', saveDraft));
      $('publishSettingsBtn').addEventListener('click', () => runUiAction('publishSettingsBtn', 'Publishing...', publishSettings));
      $('retryPublishVerificationBtn').addEventListener('click', () => retryPublishVerification().catch(reportApiError));
      $('settingLogoFile').addEventListener('change', () => uploadLogo().catch(reportApiError));
      $('settingHeroImageFile').addEventListener('change', () => uploadWebsiteImage('hero', 'settingHeroImageFile', 'settingHeroImageUrl').catch(reportApiError));
      $('settingPrincipalImageFile').addEventListener('change', () => uploadWebsiteImage('principal', 'settingPrincipalImageFile', 'settingPrincipalImageUrl').catch(reportApiError));
      $('settingAboutImageFile').addEventListener('change', () => uploadAboutImage().catch(reportApiError));
      $('showcaseAddCategory').addEventListener('click', () => {
        if (showcaseCategories.length >= SHOWCASE_CATEGORY_LIMIT) return;
        // No id: the server mints one on save and the console keeps whatever
        // it is told. Inventing one here would be a second authority on it.
        showcaseCategories.push({ id: '', label: { zh: '', en: '' } });
        renderShowcaseCategories();
        renderShowcaseItems();
        setSettingsDirty(true);
        $(`showcaseCategory${showcaseCategories.length - 1}`)?.focus();
      });
      const dropzone = $('showcaseDropzone');
      const filePicker = $('showcaseFiles');
      dropzone.addEventListener('click', () => filePicker.click());
      // Keyboard parity: the dropzone is a real control, so it answers the
      // keys a control answers to. Drag and drop alone is mouse-only.
      dropzone.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); filePicker.click(); }
      });
      filePicker.addEventListener('change', () => {
        const chosen = filePicker.files;
        addShowcaseFiles(chosen).catch(reportApiError);
        filePicker.value = '';
      });
      ['dragenter', 'dragover'].forEach((name) => dropzone.addEventListener(name, (event) => {
        event.preventDefault();
        dropzone.classList.add('is-over');
      }));
      ['dragleave', 'drop'].forEach((name) => dropzone.addEventListener(name, (event) => {
        event.preventDefault();
        dropzone.classList.remove('is-over');
      }));
      dropzone.addEventListener('drop', (event) => {
        addShowcaseFiles(event.dataTransfer?.files).catch(reportApiError);
      });
      $('showcaseAddItem').addEventListener('click', () => {
        showcaseItems.push({ image_url: '', category_id: '',
          title: { zh: '', en: '' }, caption: { zh: '', en: '' }, video_url: '',
          featured_rank: null,
          publication_state: defaultShowcasePublicationState() });
        renderShowcaseItems();
        setSettingsDirty(true);
        // Focus the new card's first text field, so adding a work and typing
        // is one gesture rather than add-then-hunt.
        $(`showcaseTitle${showcaseItems.length - 1}`)?.focus();
      });
      $('refreshAnalyticsBtn').addEventListener('click', () => loadAnalytics().catch((err) => showToast(err.message, 'error')));
      $('analyticsDays').addEventListener('change', () => loadAnalytics().catch((err) => showToast(err.message, 'error')));
      $('refreshAuditBtn').addEventListener('click', loadAuditLogs);
      let auditFilterTimer = null;
      $('auditActionFilter').addEventListener('input', () => {
        clearTimeout(auditFilterTimer);
        auditFilterTimer = setTimeout(loadAuditLogs, 350);
      });
      $('resetPresetBtn').addEventListener('click', applyCategoryPreset);
      $('undoPresetBtn').addEventListener('click', () => {
        if (!lastPresetSnapshot) return;
        const snapshot = lastPresetSnapshot;
        lastPresetSnapshot = null;
        applyDraftToEditor(snapshot);
        $('presetUndoBar').classList.add('hidden');
        setSettingsDirty(true);
        showToast('Previous draft choices restored.');
      });
      $('addRegistrationQuestionBtn').addEventListener('click', addRegistrationQuestion);
      $('addFaqItemBtn').addEventListener('click', addFaqItem);
      $('resetMessageTemplatesBtn').addEventListener('click', () => {
        fillMessageTemplates(defaultMessageTemplates());
        setSettingsDirty(true);
      });
      document.querySelectorAll('[data-workbench-tab]').forEach((button) => {
        button.addEventListener('click', () => switchWorkbenchTab(button.dataset.workbenchTab));
      });
      document.querySelector('.workbench-nav-list').addEventListener('keydown', (event) => {
        if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) return;
        const tabs = Array.from(document.querySelectorAll('[data-workbench-tab]'));
        const index = tabs.indexOf(document.activeElement);
        if (index === -1) return;
        event.preventDefault();
        const forward = event.key === 'ArrowRight' || event.key === 'ArrowDown';
        const next = tabs[(index + (forward ? 1 : tabs.length - 1)) % tabs.length];
        next.focus();
        switchWorkbenchTab(next.dataset.workbenchTab, {focus: false});
      });
      document.querySelectorAll('[data-preview-mode]').forEach((button) => {
        button.addEventListener('click', () => switchPreviewMode(button.dataset.previewMode));
      });
      document.querySelectorAll('[data-preview-source]').forEach((button) => {
        button.addEventListener('click', () => switchPreviewSource(button.dataset.previewSource));
      });
      document.querySelectorAll('[data-preview-device]').forEach((button) => {
        button.addEventListener('click', () => switchPreviewDevice(button.dataset.previewDevice));
      });
      document.querySelectorAll('[data-preview-language]').forEach((button) => {
        button.addEventListener('click', () => switchPreviewLanguage(button.dataset.previewLanguage, {manual: true}));
      });
      $('presetGrid').addEventListener('click', (event) => {
        const card = event.target.closest('[data-preset-key]');
        if (!card) return;
        $('settingCategory').value = card.dataset.presetKey;
        applyCategoryPreset();
      });
      $('stylePresetSelect').addEventListener('change', () => applyVisualStyle($('stylePresetSelect').value));
      /* Picking a card applies that whole theme. Custom is the one card that
         does not carry a palette of its own — it hands over to the picker. */
      $('themeGrid').addEventListener('click', (event) => {
        const card = event.target.closest('[data-style-key]');
        if (!card) return;
        clearTimeout(accentPreviewTimer);
        applyVisualStyle(card.dataset.styleKey);
      });
      /* The accent knob, revealed only under Custom. `input` fires
         continuously while the swatch is dragged, so the request is debounced
         and stale replies are dropped by sequence number — see previewAccent. */
      $('accentSourceSwatch').addEventListener('input', (event) => {
        $('accentSourceHex').value = event.target.value.toUpperCase();
        requestAccentPreview(event.target.value);
      });
      $('accentSourceHex').addEventListener('input', (event) => {
        const value = event.target.value.trim();
        if (/^#[0-9a-f]{6}$/i.test(value)) requestAccentPreview(value);
      });
      $('accentSourceHex').addEventListener('blur', () => syncAccentPicker($('settingPrimaryColor').value));
      $('accentFromLogoBtn').addEventListener('click', () => {
        const isZh = adminIsZh();
        const url = $('settingLogoUrl')?.value?.trim();
        if (!url) {
          showToast(isZh ? '先上传 Logo，再从它取色。' : 'Upload a logo first, then take the colour from it.');
          return;
        }
        const image = new Image();
        image.crossOrigin = 'anonymous';
        image.onload = () => {
          const picked = dominantHexFromImage(image);
          if (!picked) {
            showToast(isZh ? '这个 Logo 里没有足够的颜色可取。' : 'That logo has no strong colour to take.');
            return;
          }
          $('accentSourceSwatch').value = picked;
          $('accentSourceHex').value = picked;
          previewAccent(picked);
        };
        image.onerror = () => showToast(isZh ? '读不到这个 Logo。' : 'That logo could not be read.');
        image.src = url;
      });
      $('settingColorScheme').addEventListener('change', () => {
        const chosen = $('settingColorScheme').value;
        activeSchemePreference = chosen;
        /* `system` is not a palette. The preview has to show one of the two, so
           it keeps showing whichever is current and the note explains that the
           visitor's device decides on the live site. */
        applyVisualStyle(activeVisualStyle, {scheme: chosen === 'system' ? null : chosen});
      });
      document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && $('modalOverlay').classList.contains('active')) closeModal();
      });
      $('registrationFieldsEditor').addEventListener('click', (event) => {
        const remove = event.target.closest('[data-remove-registration]');
        if (remove) removeRegistrationQuestion(remove.dataset.removeRegistration);
      });
      $('faqItemsEditor').addEventListener('click', (event) => {
        const remove = event.target.closest('[data-remove-faq]');
        if (remove) removeFaqItem(remove.dataset.removeFaq);
      });
      $('registrationFieldsEditor').addEventListener('input', () => { setSettingsDirty(true); updateThemePreview(); });
      $('registrationFieldsEditor').addEventListener('change', () => { setSettingsDirty(true); updateThemePreview(); });
      $('faqItemsEditor').addEventListener('input', () => { setSettingsDirty(true); updateThemePreview(); });
      [
        'settingName','settingLogoUrl','settingPrimaryColor','settingSecondaryColor','settingWelcome','settingSlogan',
        'settingPortalLabel','settingRegisterIntro','settingRegistrationTitle','settingPhone','settingEmail','settingAddress','settingTimezone',
        'settingHeroEyebrow','settingHeroTitle','settingHeroTitleEn','settingHeroSubtitle','settingHeroSubtitleEn','settingHeroImageUrl',
        'settingPrimaryCta','settingPrimaryCtaEn','settingSecondaryCta','settingSecondaryCtaEn','settingSecondaryCtaHref',
        'settingRegistrationTitleEn','settingRegisterIntroEn',
        'settingSloganEn','settingWelcomeEn',
        'settingCoursesLabel','settingGalleryLabel','settingFaqLabel','settingContactLabel',
        'settingCoursesLabelEn','settingGalleryLabelEn','settingFaqLabelEn','settingContactLabelEn',
        'settingPrincipalName','settingPrincipalTitle','settingPrincipalTitleEn','settingPrincipalBio','settingPrincipalBioEn',
        'settingPrincipalQuote','settingPrincipalQuoteEn','settingPrincipalImageUrl',
        'settingAboutEyebrow','settingAboutEyebrowEn','settingAboutTitle','settingAboutTitleEn',
        'settingAboutBody','settingAboutBodyEn','settingSeoTitle','settingSeoDescription',
        'settingShowcaseLabel','settingShowcaseLabelEn','settingShowcaseTitle','settingShowcaseTitleEn',
        'settingShowcaseLead','settingShowcaseLeadEn',
        'settingThemeBackground','settingThemePanel','settingThemeText','settingThemeMuted','settingThemeBorder',
        'settingTimetableWeeks','settingTimetableLabel','settingTimetableLabelEn','settingTimetableLead','settingTimetableLeadEn',
        'messageCheckin','messageCheckinEmpty','messageTopup','messageRenewal','messageBirthday'
      ].forEach((id) => $(id).addEventListener('input', () => { setSettingsDirty(true); updateThemePreview(); }));
      ['settingAboutTitle','settingAboutTitleEn','settingAboutBody','settingAboutBodyEn']
        .forEach((id) => $(id).addEventListener('input', renderAboutReadiness));
      // Inline validation errors clear as soon as the owner edits the field.
      BRAND_ERROR_FIELDS.forEach((id) => $(id).addEventListener('input', () => clearFieldError(id)));
      [
        'settingPrimaryColor','settingSecondaryColor','settingThemeBackground','settingThemePanel',
        'settingThemeText','settingThemeMuted','settingThemeBorder'
      ].forEach((id) => $(id).addEventListener('input', markThemeCustom));
      $('settingShowWelcome').addEventListener('change', () => { setSettingsDirty(true); updateThemePreview(); });
      [
        'settingHeroStyle','settingHeroShape','settingShowStudentLogin','settingSecondaryCtaTarget','settingButtonStyle','settingFontMood',
        'settingShowPrincipal','settingShowCourses','settingShowGallery','settingShowFaq','settingShowContact','settingShowStudentArea',
        'settingShowAbout','settingShowShowcase',
        'settingCmsLayout','settingShowTimetable','settingShowTimetableBooking',
        'settingTimetableFieldTeacher','settingTimetableFieldRoom','settingTimetableFieldAgeRange',
        'settingTimetableFieldDuration','settingTimetableFieldCapacity','settingTimetableFieldPrice'
      ].forEach((id) => $(id).addEventListener('change', () => { setSettingsDirty(true); updateThemePreview(); }));
      $('settingSecondaryCtaTarget').addEventListener('change', () => {
        $('settingSecondaryCtaHrefGroup').hidden = $('settingSecondaryCtaTarget').value !== 'external';
      });
      ['settingButtonStyle','settingFontMood'].forEach((id) => $(id).addEventListener('change', markThemeCustom));
      document.addEventListener('studiosaas:admin-language', (event) => {
        if (!previewLanguageManuallySet) {
          switchPreviewLanguage(event.detail?.language);
        }
        renderStylePresetGrid();
        renderPresetGrid($('settingCategory')?.value || 'general');
        updateWorkspaceStatus();
        updateSurfaceHealth().catch((error) => console.warn('Surface health language refresh failed.', error));
      });
      $('settingCategory').addEventListener('change', () => {
        applyCategoryPreset();
      });
      updateSurfaceLinks();
      document.querySelectorAll('.nav-link').forEach((link) => {
        link.addEventListener('click', (event) => {
          const workbenchTab = link.dataset.workbenchShortcut;
          if (workbenchTab) {
            event.preventDefault();
            switchWorkbenchTab(workbenchTab);
            $('section-settings')?.scrollIntoView({behavior: 'smooth', block: 'start'});
          }
          document.querySelectorAll('.nav-link').forEach((item) => item.classList.remove('active'));
          link.classList.add('active');
        });
      });
      $('modalOverlay').addEventListener('click', (event) => {
        if (event.target === $('modalOverlay')) closeModal();
      });
      $('modalOverlay').addEventListener('keydown', trapModalFocus);
    }

    /* The header is one wrapping row, so its height is a fact about the
       rendered page rather than a constant: it grows when the nav wraps, when
       the studio name is long, and when the language switch is wider in one
       language than the other. The sticky preview column and every section's
       scroll-margin read --header-h, so it is measured instead of guessed. */
    function syncHeaderOffset() {
      const header = document.querySelector('.header');
      if (!header) return;
      const height = Math.round(header.getBoundingClientRect().height);
      document.documentElement.style.setProperty('--header-h', `${height}px`);
    }

    bindEvents();
    syncHeaderOffset();
    window.addEventListener('popstate', () => switchWorkbenchTab(requestedWorkbenchTab(), {syncUrl: false}));
    if ('ResizeObserver' in window) {
      new ResizeObserver(syncHeaderOffset).observe(document.querySelector('.header'));
    } else {
      window.addEventListener('resize', syncHeaderOffset);
    }
    updateProducerCredit().catch((error) => console.warn('Producer credit refresh failed.', error));
    window.addEventListener('beforeunload', (event) => {
      if (!settingsDirty) return;
      event.preventDefault();
      event.returnValue = '';
    });
    loadIndustryPresets().then(checkSession);
