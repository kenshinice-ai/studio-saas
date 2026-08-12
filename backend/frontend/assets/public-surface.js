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
    style.textContent = 'html[data-public-surface-loading="true"] #navPrincipal,html[data-public-surface-loading="true"] #navShowcase,html[data-public-surface-loading="true"] #navCourses,html[data-public-surface-loading="true"] #navTimetable,html[data-public-surface-loading="true"] #navGallery,html[data-public-surface-loading="true"] #navFaq,html[data-public-surface-loading="true"] #navStudent,html[data-public-surface-loading="true"] #navPrimaryCta,html[data-public-surface-loading="true"] #heroSecondaryCta,html[data-public-surface-loading="true"] #mnavPrincipal,html[data-public-surface-loading="true"] #mnavShowcase,html[data-public-surface-loading="true"] #mnavCourses,html[data-public-surface-loading="true"] #mnavTimetable,html[data-public-surface-loading="true"] #mnavGallery,html[data-public-surface-loading="true"] #mnavFaq,html[data-public-surface-loading="true"] #mnavStudent,html[data-public-surface-loading="true"] #mnavPrimaryCta,html[data-public-surface-loading="true"] #footShowcase,html[data-public-surface-loading="true"] #footCourses,html[data-public-surface-loading="true"] #footTimetable,html[data-public-surface-loading="true"] #footGallery,html[data-public-surface-loading="true"] #footFaq,html[data-public-surface-loading="true"] #footStudent,html[data-public-surface-loading="true"] #footRegister{visibility:hidden!important}';
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
  const localizedOf = (brand) => brand?.localizedCopy || brand?.localized_copy || {};
  const pairText = (value) => value && typeof value === 'object'
    ? text(value.zh || value.en)
    : text(value);

  // Kept in step with NAV_LABEL_LIMIT in api_v1.py. A studio names its own
  // sections and those names are also its nav items; one studio's English
  // course label is the full list of media it teaches, at 74 characters. The
  // heading on the page keeps the sentence, the bar gets an entry.
  const NAV_LABEL_LIMIT = { zh: 10, en: 24 };
  const clipNavLabel = (value, language) => {
    const limit = NAV_LABEL_LIMIT[language] || 24;
    const source = text(value);
    return source.length <= limit ? source : `${source.slice(0, limit - 1).trimEnd()}…`;
  };

  function entry(key, intent, ready, href, reasonCode, nextAction, options) {
    const config = options || {};
    const contentReady = config.contentReady === undefined ? Boolean(ready) : Boolean(config.contentReady);
    const dependencyReady = config.dependencyReady === undefined ? Boolean(ready) : Boolean(config.dependencyReady);
    const effectiveReady = Boolean(ready && contentReady && dependencyReady);
    const visible = Boolean(intent && effectiveReady);
    return {
      key, intent: Boolean(intent), ready: effectiveReady, contentReady, dependencyReady, visible,
      href, surface: config.surface || key, placement: config.placement || 'home',
      navigationEligible: config.navigationEligible !== false,
      footerEligible: config.footerEligible !== false,
      ...(config.label ? { label: config.label } : {}),
      reasonCode: visible ? 'ready' : (intent ? (reasonCode || 'no_content') : 'disabled_by_owner'),
      nextAction: visible ? '' : (nextAction || 'review_in_studio_admin'),
      publishedVersion: config.publishedVersion ?? null,
    };
  }

  function fact(input, key, fallback) {
    const value = input?.moduleFacts?.[key];
    return typeof value === 'boolean' ? value : Boolean(fallback);
  }

  function actionsFor(hero, modules) {
    const primaryModule = modules.register;
    const primary = {
      key: 'primary', targetType: 'register', href: primaryModule.href,
      visible: primaryModule.visible, reasonCode: primaryModule.reasonCode,
      nextAction: primaryModule.nextAction,
    };
    const requested = text(hero.secondary_cta_target || hero.secondaryCtaTarget || 'auto').toLowerCase();
    if (requested === 'hidden') {
      return { primary, secondary: { key: 'secondary', targetType: 'hidden', href: '', visible: false,
        reasonCode: 'disabled_by_owner', nextAction: 'choose_secondary_cta_target' } };
    }
    if (requested === 'external') {
      const candidate = text(hero.secondary_cta_href || hero.secondaryCtaHref);
      const href = /^https:\/\/\S+$/i.test(candidate) ? candidate : '';
      return { primary, secondary: { key: 'secondary', targetType: 'external', href,
        visible: Boolean(href), reasonCode: href ? 'ready' : 'missing_external_url',
        nextAction: href ? '' : 'add_secondary_cta_url' } };
    }
    const choices = ['courses', 'showcase', 'timetable', 'register'];
    const target = requested === 'auto'
      ? (choices.find((key) => modules[key].visible) || 'register')
      : (choices.includes(requested) ? requested : 'register');
    const module = modules[target];
    return { primary, secondary: { key: 'secondary', targetType: target, href: module.href,
      visible: module.visible, reasonCode: module.reasonCode, nextAction: module.nextAction } };
  }

  function resolve(input) {
    const brand = input?.brand || {};
    const website = websiteOf(brand);
    const hero = heroOf(brand);
    const principal = principalOf(brand);
    const registration = profileOf(brand);
    const localized = localizedOf(brand);
    const showcase = input?.showcase || {};
    const programs = input?.programs || {};
    const gallery = input?.gallery || {};
    const timetable = input?.timetable || {};
    const faqItems = list(brand.faqItems || brand.faq_items);
    const publishedVersion = input?.publishedVersion ?? brand.publishedVersion ?? null;
    const workNoun = brand.workNoun || brand.work_noun || { zh: '作品', en: 'work', en_plural: 'works' };
    const venueNoun = brand.venueNoun || brand.venue_noun || { zh: '工作室', en: 'studio' };
    const nouns = (value, language) => {
      let result = text(value);
      const work = text(workNoun[language] || workNoun.zh || '作品');
      const works = language === 'en'
        ? text(workNoun.en_plural || workNoun.en || work || 'works')
        : work;
      const venue = text(venueNoun[language] || venueNoun.zh || '工作室');
      return result.split('%WORKS%').join(works).split('%WORK%').join(work).split('%VENUE%').join(venue);
    };
    const label = (value, fallbackZh, fallbackEn) => ({
      zh: clipNavLabel(nouns(pairText(value) || fallbackZh, 'zh'), 'zh'),
      en: clipNavLabel(nouns((value && typeof value === 'object' ? text(value.en || value.zh) : text(value)) || fallbackEn, 'en'), 'en'),
    });
    const labels = {
      principal: { zh: '主理人', en: 'Principal' },
      showcase: label(website.showcase_label || website.showcaseLabel, '工作室作品', 'Selected Work'),
      courses: label(localized.courses_label || localized.coursesLabel, '课程与班次', 'Courses & Classes'),
      timetable: label(website.timetable_label || website.timetableLabel, '课程安排', 'Timetable'),
      gallery: label(localized.gallery_label || localized.galleryLabel, '学员作品', 'Student Works'),
      faq: label(localized.faq_label || localized.faqLabel, '常见问题', 'Questions & Answers'),
      student: { zh: '学员专区', en: 'Student Login' },
      register: label(localized.primary_cta || localized.primaryCta, '预约体验', 'Book a Trial'),
    };
    const contactReady = Boolean(text(brand.contactPhone || brand.contact_phone)
      || text(brand.contactEmail || brand.contact_email)
      || text(brand.address));
    const principalReady = Boolean(pairText(principal.bio));
    const showcaseItems = list(showcase.items);
    const showcaseReady = Boolean(showcase.enabled && (showcase.total || showcaseItems.length));
    const courseItems = list(programs.programs || programs.items);
    const galleryItems = list(gallery.items);
    const timetableReady = Boolean(timetable.enabled && list(timetable.days).some((day) => list(day.classes).length));
    const aboutReady = Boolean(pairText(website.about_title || website.aboutTitle)
      || pairText(website.about_body || website.aboutBody)
      || list(website.about_images || website.aboutImages).length
      || list(website.about_items || website.aboutItems).length);
    const studentIntent = bool(website.show_student_area ?? website.showStudentArea
      ?? hero.show_student_login ?? hero.showStudentLogin, true);
    const modules = {
      about: entry('about', bool(website.show_about ?? website.showAbout, false), aboutReady,
        '#home:about', 'missing_about_content', 'complete_space_profile', {
          surface: 'home', placement: 'after_hero', navigationEligible: false, footerEligible: false,
          publishedVersion,
        }),
      principal: entry('principal', bool(website.show_principal ?? website.showPrincipal, true),
        fact(input, 'principal', principalReady), '#home:artist', 'missing_content', 'add_principal_bio', {
          surface: 'home', placement: 'after_about', footerEligible: false, publishedVersion, label: labels.principal,
        }),
      showcase: entry('showcase', bool(website.show_showcase ?? website.showShowcase, false),
        fact(input, 'showcase', showcaseReady),
        `/${encodeURIComponent(input?.slug || '')}/showcase`, showcase.enabled ? 'no_published_works' : 'not_published',
        'publish_showcase_work', { surface: 'showcase', placement: 'after_principal', publishedVersion, label: labels.showcase }),
      courses: entry('courses', bool(website.show_courses ?? website.showCourses, true),
        fact(input, 'courses', courseItems.length > 0), '#home:courses', 'no_published_courses', 'publish_course', {
          surface: 'home', placement: 'after_showcase', publishedVersion, label: labels.courses,
        }),
      timetable: entry('timetable', bool(website.show_timetable ?? website.showTimetable, false),
        fact(input, 'timetable', timetableReady),
        `/${encodeURIComponent(input?.slug || '')}/timetable`, timetable.enabled ? 'no_upcoming_classes' : 'not_published',
        'publish_timetable', { surface: 'timetable', placement: 'navigation', publishedVersion, label: labels.timetable }),
      gallery: entry('gallery', bool(website.show_gallery ?? website.showGallery, true),
        fact(input, 'gallery', galleryItems.length > 0), '#home:gallery', 'no_consented_student_work', 'share_student_work', {
          surface: 'home', placement: 'after_courses', publishedVersion, label: labels.gallery,
        }),
      faq: entry('faq', bool(website.show_faq ?? website.showFaq, true), faqItems.length > 0,
        '#home:faq', 'no_faq_content', 'add_faq', { surface: 'home', placement: 'after_gallery', publishedVersion, label: labels.faq }),
      contact: entry('contact', bool(website.show_contact ?? website.showContact, true), contactReady,
        '#home:contact', 'missing_contact_details', 'add_contact_details', {
          surface: 'home', placement: 'after_faq', navigationEligible: false, footerEligible: false, publishedVersion,
        }),
      student: entry('student', studentIntent, true, '#my', '', '', {
        surface: 'home', placement: 'utility', publishedVersion, label: labels.student,
      }),
      register: entry('register', true, Boolean(Object.keys(registration).length || brand.name),
        '#join', 'registration_unavailable', 'complete_registration_profile', {
        surface: 'register', placement: 'action', publishedVersion, label: labels.register,
        }),
    };
    const navigation = Object.values(modules).filter((module) => module.navigationEligible);
    const footer = Object.values(modules).filter((module) => module.footerEligible);
    const actions = actionsFor(hero, modules);
    if (modules.register?.label) actions.primary.label = modules.register.label;
    if (actions.secondary && !actions.secondary.label) {
      const requested = text(hero.secondary_cta_target || hero.secondaryCtaTarget || 'auto').toLowerCase();
      actions.secondary.label = requested === 'showcase' ? modules.showcase.label
        : requested === 'timetable' ? modules.timetable.label
        : requested === 'register' ? modules.register.label
        : { zh: '查看课程', en: 'Explore Programs' };
    }
    return { version: 3, contractVersion: 3, generatedAt: new Date().toISOString(), publishedVersion,
      modules, navigation, footer, actions, shell: { navigation, footer, actions } };
  }

  function clearLoading() {
    if (global.document) delete global.document.documentElement.dataset.publicSurfaceLoading;
  }

  function apply(contract, root) {
    const scope = root || document;
    if (!contract?.modules) return;
    clearLoading();
    const currentPath = String(global.location?.pathname || '');
    const currentSearch = String(global.location?.search || '');
    const tenantSlug = scope.body?.dataset?.tenantSlug || '';
    const tenantHome = tenantSlug ? `/${encodeURIComponent(tenantSlug)}` : '';
    const samePath = (a, b) => String(a).replace(/\/+$/, '') === String(b).replace(/\/+$/, '');
    const pathOf = (href) => {
      try {
        return new URL(href, global.location?.href || 'https://surface.invalid').pathname;
      } catch (error) {
        return '';
      }
    };
    const onTenantHome = Boolean(tenantHome) && samePath(currentPath, tenantHome);
    // The visitor's language is worth carrying to the next page; a category
    // filter belongs to the page that owns it and is not.
    const langQuery = (() => {
      try {
        const value = new URLSearchParams(currentSearch).get('lang');
        return value ? `?lang=${encodeURIComponent(value)}` : '';
      } catch (error) {
        return '';
      }
    })();
    const hrefForPage = (href) => {
      const value = text(href);
      if (!value || !value.startsWith('#') || !tenantHome) return value;
      // Hash-only links work on the home page but not on /showcase, /timetable
      // or /register, so away from home they name the home page first.
      //
      // On the home page they must be left alone apart from reproducing the
      // current query. Prefixing unconditionally was the bug: `/slug#home:faq`
      // differs from `/slug?lang=en` by more than its fragment, so the browser
      // treated every nav click as a new document — a full reload that also
      // dropped the visitor's language and whatever utm_* they arrived with.
      if (onTenantHome) return `${currentPath}${currentSearch}${value}`;
      return `${tenantHome}${langQuery}${value}`;
    };
    const setLabel = (node, label) => {
      if (!node || !label) return;
      const zh = text(label.zh || label.en);
      const en = text(label.en || label.zh);
      if (!zh && !en) return;
      node.setAttribute('data-zh', zh || en);
      node.setAttribute('data-en', en || zh);
      const language = String(scope.documentElement?.lang || '').toLowerCase().startsWith('en') ? 'en' : 'zh';
      node.textContent = language === 'en' ? (en || zh) : (zh || en);
    };
    const ids = {
      principal: ['navPrincipal', 'mnavPrincipal'],
      showcase: ['navShowcase', 'mnavShowcase', 'footShowcase'],
      courses: ['navCourses', 'mnavCourses', 'footCourses'],
      timetable: ['navTimetable', 'mnavTimetable', 'footTimetable'],
      gallery: ['navGallery', 'mnavGallery', 'footGallery'],
      faq: ['navFaq', 'mnavFaq', 'footFaq'],
      student: ['navStudent', 'mnavStudent', 'footStudent'],
      register: ['navPrimaryCta', 'mnavPrimaryCta', 'footRegister'],
    };
    Object.entries(ids).forEach(([key, names]) => {
      const module = contract.modules[key];
      names.forEach((id) => {
        const node = scope.getElementById ? scope.getElementById(id) : null;
        if (!node) return;
        const visible = Boolean(module?.visible);
        node.style.display = visible ? '' : 'none';
        node.setAttribute('aria-hidden', visible ? 'false' : 'true');
        if (visible && node.tagName === 'A' && module?.href) node.href = hrefForPage(module.href);
        if (!visible) node.setAttribute('tabindex', '-1');
        else node.removeAttribute('tabindex');
        // The pages share one entry list now, so no entry can be born knowing
        // which page it is on. Whichever one resolves to the current path is
        // the current page, and only that one.
        if (node.tagName === 'A') {
          const raw = node.getAttribute('href') || '';
          if (!raw.startsWith('#') && pathOf(raw) && samePath(pathOf(raw), currentPath)) {
            node.setAttribute('aria-current', 'page');
          } else {
            node.removeAttribute('aria-current');
          }
        }
        setLabel(node, module?.label);
        if (visible && node.tagName === 'A' && node.getAttribute('href') === '#home:' + key) {
          node.dataset.surfaceReady = 'true';
        }
      });
    });
    const primary = contract.actions?.primary;
    ['navPrimaryCta', 'mnavPrimaryCta', 'footRegister'].forEach((id) => {
      const node = scope.getElementById ? scope.getElementById(id) : null;
      if (node) {
        setLabel(node, primary?.label);
        if (primary?.visible && primary?.href) node.href = hrefForPage(primary.href);
      }
    });
    const secondary = contract.actions?.secondary;
    const secondaryNode = scope.getElementById ? scope.getElementById('heroSecondaryCta') : null;
    if (secondaryNode) {
      secondaryNode.style.display = secondary?.visible ? '' : 'none';
      secondaryNode.setAttribute('aria-hidden', secondary?.visible ? 'false' : 'true');
      if (secondary?.visible) {
        secondaryNode.href = hrefForPage(secondary.href);
        setLabel(secondaryNode, secondary.label);
        secondaryNode.dataset.analyticsLabel = `hero_${secondary.targetType}`;
        secondaryNode.removeAttribute('tabindex');
      } else {
        secondaryNode.setAttribute('tabindex', '-1');
      }
    }
    scope.querySelectorAll?.('[data-surface-key]').forEach((node) => {
      const module = contract.modules[node.dataset.surfaceKey];
      if (module) node.hidden = !module.visible;
    });
    // Anything outside the entry list that still claims to be the current page.
    // The old test asked whether the href contained the last path segment; on a
    // tenant home page that segment is the slug, and every resolved href starts
    // with it, so the test was true for every link on the page.
    scope.querySelectorAll?.('a[aria-current="page"]').forEach((node) => {
      const raw = node.getAttribute('href') || '';
      if (!raw || raw.startsWith('#')) return;
      const target = pathOf(raw);
      if (target && !samePath(target, currentPath)) node.removeAttribute('aria-current');
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
