/* Shared public-surface contract for tenant pages.
 *
 * The public shell has one source of truth for whether an entry is intended,
 * actually ready, and safe to expose.  A toggle alone is not enough: a link to
 * an empty course section or an unpublished timetable is a broken promise.
 * This runtime stays framework-free because the tenant templates are served as
 * HTML, but exposes a small typed-by-convention contract to every page.
 */
(function (global) {
  'use strict';

  if (global.document) {
    global.document.documentElement.dataset.publicSurfaceLoading = 'true';
    const style = global.document.createElement('style');
    style.textContent = 'html[data-public-surface-loading="true"] #navPrincipal,html[data-public-surface-loading="true"] #navShowcase,html[data-public-surface-loading="true"] #navCourses,html[data-public-surface-loading="true"] #navTimetable,html[data-public-surface-loading="true"] #navGallery,html[data-public-surface-loading="true"] #navFaq,html[data-public-surface-loading="true"] #navStudent,html[data-public-surface-loading="true"] #navPrimaryCta,html[data-public-surface-loading="true"] #mnavPrincipal,html[data-public-surface-loading="true"] #mnavShowcase,html[data-public-surface-loading="true"] #mnavCourses,html[data-public-surface-loading="true"] #mnavTimetable,html[data-public-surface-loading="true"] #mnavGallery,html[data-public-surface-loading="true"] #mnavFaq,html[data-public-surface-loading="true"] #mnavStudent,html[data-public-surface-loading="true"] #mnavPrimaryCta{visibility:hidden!important}';
    global.document.head.appendChild(style);
  }

  const text = (value) => String(value == null ? '' : value).trim();
  const bool = (value, fallback) => {
    if (value === undefined || value === null || value === '') return fallback;
    if (typeof value === 'boolean') return value;
    return !['false', '0', 'off', 'no'].includes(text(value).toLowerCase());
  };
  const list = (value) => Array.isArray(value) ? value : [];
  const websiteOf = (brand) => brand?.websiteProfile || brand?.website_profile || {};
  const heroOf = (brand) => brand?.heroProfile || brand?.hero_profile || {};
  const principalOf = (brand) => brand?.principalProfile || brand?.principal_profile || {};
  const profileOf = (brand) => brand?.registrationProfile || brand?.registration_profile || {};
  const pairText = (value) => value && typeof value === 'object'
    ? text(value.zh || value.en)
    : text(value);

  function entry(key, intent, ready, href, reasonCode, nextAction, surface) {
    const visible = Boolean(intent && ready);
    return {
      key, intent: Boolean(intent), ready: Boolean(ready), visible,
      href, surface: surface || key,
      reasonCode: visible ? 'ready' : (intent ? (reasonCode || 'no_content') : 'disabled_by_owner'),
      nextAction: visible ? '' : (nextAction || 'review_in_studio_admin'),
    };
  }

  function resolve(input) {
    const brand = input?.brand || {};
    const website = websiteOf(brand);
    const hero = heroOf(brand);
    const principal = principalOf(brand);
    const registration = profileOf(brand);
    const showcase = input?.showcase || {};
    const programs = input?.programs || {};
    const gallery = input?.gallery || {};
    const timetable = input?.timetable || {};
    const faqItems = list(brand.faqItems || brand.faq_items);
    const contactReady = Boolean(text(brand.contactPhone || brand.contact_phone)
      || text(brand.contactEmail || brand.contact_email)
      || text(brand.address));
    const principalReady = Boolean(pairText(principal.bio));
    const showcaseItems = list(showcase.items);
    const showcaseReady = Boolean(showcase.enabled && (showcase.total || showcaseItems.length));
    const courseItems = list(programs.programs || programs.items);
    const galleryItems = list(gallery.items);
    const timetableReady = Boolean(timetable.enabled && list(timetable.days).some((day) => list(day.classes).length));
    const studentIntent = bool(website.show_student_area ?? website.showStudentArea
      ?? hero.show_student_login ?? hero.showStudentLogin, true);
    const modules = {
      principal: entry('principal', bool(website.show_principal ?? website.showPrincipal, true), principalReady,
        '#home:artist', principalReady ? '' : 'missing_content', 'add_principal_bio', 'home'),
      showcase: entry('showcase', bool(website.show_showcase ?? website.showShowcase, false), showcaseReady,
        `/${encodeURIComponent(input?.slug || '')}/showcase`, showcase.enabled ? 'no_published_works' : 'not_published',
        'publish_showcase_work', 'showcase'),
      courses: entry('courses', bool(website.show_courses ?? website.showCourses, true), courseItems.length > 0,
        '#home:courses', 'no_published_courses', 'publish_course', 'home'),
      timetable: entry('timetable', bool(website.show_timetable ?? website.showTimetable, false), timetableReady,
        `/${encodeURIComponent(input?.slug || '')}/timetable`, timetable.enabled ? 'no_upcoming_classes' : 'not_published',
        'publish_timetable', 'timetable'),
      gallery: entry('gallery', bool(website.show_gallery ?? website.showGallery, true), galleryItems.length > 0,
        '#home:gallery', 'no_consented_student_work', 'share_student_work', 'home'),
      faq: entry('faq', bool(website.show_faq ?? website.showFaq, true), faqItems.length > 0,
        '#home:faq', 'no_faq_content', 'add_faq', 'home'),
      contact: entry('contact', bool(website.show_contact ?? website.showContact, true), contactReady,
        '#home:contact', 'missing_contact_details', 'add_contact_details', 'home'),
      student: entry('student', studentIntent, true, '#my', '', '', 'home'),
      register: entry('register', true, Boolean(Object.keys(registration).length || brand.name),
        '#join', 'registration_unavailable', 'complete_registration_profile', 'register'),
    };
    const navigation = ['principal', 'showcase', 'courses', 'timetable', 'gallery', 'faq', 'student', 'register']
      .map((key) => modules[key]);
    const footer = ['showcase', 'courses', 'timetable', 'gallery', 'faq', 'student', 'register']
      .map((key) => modules[key]);
    return { version: 1, generatedAt: new Date().toISOString(), modules, navigation, footer };
  }

  function clearLoading() {
    if (global.document) delete global.document.documentElement.dataset.publicSurfaceLoading;
  }

  function apply(contract, root) {
    const scope = root || document;
    if (!contract?.modules) return;
    clearLoading();
    const ids = {
      principal: ['navPrincipal', 'mnavPrincipal', 'footPrincipal'],
      showcase: ['navShowcase', 'mnavShowcase', 'footShowcase'],
      courses: ['navCourses', 'mnavCourses', 'footCourses'],
      timetable: ['navTimetable', 'mnavTimetable', 'footTimetable'],
      gallery: ['navGallery', 'mnavGallery', 'footGallery'],
      faq: ['navFaq', 'mnavFaq', 'footFaq'],
      student: ['navStudent', 'mnavStudent', 'footStudent'],
      register: ['navPrimaryCta', 'mnavPrimaryCta', 'heroRegister', 'footRegister'],
    };
    Object.entries(ids).forEach(([key, names]) => {
      const module = contract.modules[key];
      names.forEach((id) => {
        const node = scope.getElementById ? scope.getElementById(id) : null;
        if (!node) return;
        const visible = Boolean(module?.visible);
        node.style.display = visible ? '' : 'none';
        node.setAttribute('aria-hidden', visible ? 'false' : 'true');
        if (!visible) node.setAttribute('tabindex', '-1');
        else node.removeAttribute('tabindex');
        if (visible && node.tagName === 'A' && node.getAttribute('href') === '#home:' + key) {
          node.dataset.surfaceReady = 'true';
        }
      });
    });
    const currentPath = String(global.location?.pathname || '');
    scope.querySelectorAll?.('[data-surface-key]').forEach((node) => {
      const module = contract.modules[node.dataset.surfaceKey];
      if (module) node.hidden = !module.visible;
    });
    scope.querySelectorAll?.('a[aria-current="page"]').forEach((node) => {
      const href = node.getAttribute('href') || '';
      if (!href.includes(currentPath.split('/').filter(Boolean).pop() || '')) node.removeAttribute('aria-current');
    });
  }

  async function fetchContract(api, options) {
    let response;
    try {
      response = await global.fetch(`${api}/surface`, { cache: 'no-store', ...(options || {}) });
    } catch (cause) {
      const error = new Error('Public surface contract unavailable.');
      error.code = 'PUBLIC_SURFACE_UNAVAILABLE';
      error.cause = cause;
      throw error;
    }
    let data;
    try {
      data = await response.json();
    } catch (cause) {
      const error = new Error('Public surface contract returned invalid data.');
      error.code = 'PUBLIC_SURFACE_INVALID_RESPONSE';
      error.cause = cause;
      throw error;
    }
    if (!response.ok) {
      const error = new Error(data.message || data.error || 'Public surface contract unavailable.');
      error.code = data.error || 'SURFACE_UNAVAILABLE';
      throw error;
    }
    return data.contract || data.publicSurfaceContract || data;
  }

  global.StudioSaaS = global.StudioSaaS || {};
  global.StudioSaaS.publicSurface = { resolve, apply, clearLoading, fetch: fetchContract };
})(window);
