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
    style.textContent = 'html[data-public-surface-loading="true"] #navPrincipal,html[data-public-surface-loading="true"] #navShowcase,html[data-public-surface-loading="true"] #navCourses,html[data-public-surface-loading="true"] #navTimetable,html[data-public-surface-loading="true"] #navGallery,html[data-public-surface-loading="true"] #navFaq,html[data-public-surface-loading="true"] #navStudent,html[data-public-surface-loading="true"] #navPrimaryCta,html[data-public-surface-loading="true"] #heroSecondaryCta,html[data-public-surface-loading="true"] #mnavPrincipal,html[data-public-surface-loading="true"] #mnavShowcase,html[data-public-surface-loading="true"] #mnavCourses,html[data-public-surface-loading="true"] #mnavTimetable,html[data-public-surface-loading="true"] #mnavGallery,html[data-public-surface-loading="true"] #mnavFaq,html[data-public-surface-loading="true"] #mnavStudent,html[data-public-surface-loading="true"] #mnavPrimaryCta,html[data-public-surface-loading="true"] #footPrincipal,html[data-public-surface-loading="true"] #footShowcase,html[data-public-surface-loading="true"] #footCourses,html[data-public-surface-loading="true"] #footTimetable,html[data-public-surface-loading="true"] #footGallery,html[data-public-surface-loading="true"] #footFaq,html[data-public-surface-loading="true"] #footStudent,html[data-public-surface-loading="true"] #footRegister{visibility:hidden!important}';
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
    const showcase = input?.showcase || {};
    const programs = input?.programs || {};
    const gallery = input?.gallery || {};
    const timetable = input?.timetable || {};
    const faqItems = list(brand.faqItems || brand.faq_items);
    const publishedVersion = input?.publishedVersion ?? brand.publishedVersion ?? null;
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
          surface: 'home', placement: 'after_about', footerEligible: false, publishedVersion,
        }),
      showcase: entry('showcase', bool(website.show_showcase ?? website.showShowcase, false),
        fact(input, 'showcase', showcaseReady),
        `/${encodeURIComponent(input?.slug || '')}/showcase`, showcase.enabled ? 'no_published_works' : 'not_published',
        'publish_showcase_work', { surface: 'showcase', placement: 'after_principal', publishedVersion }),
      courses: entry('courses', bool(website.show_courses ?? website.showCourses, true),
        fact(input, 'courses', courseItems.length > 0), '#home:courses', 'no_published_courses', 'publish_course', {
          surface: 'home', placement: 'after_showcase', publishedVersion,
        }),
      timetable: entry('timetable', bool(website.show_timetable ?? website.showTimetable, false),
        fact(input, 'timetable', timetableReady),
        `/${encodeURIComponent(input?.slug || '')}/timetable`, timetable.enabled ? 'no_upcoming_classes' : 'not_published',
        'publish_timetable', { surface: 'timetable', placement: 'navigation', publishedVersion }),
      gallery: entry('gallery', bool(website.show_gallery ?? website.showGallery, true),
        fact(input, 'gallery', galleryItems.length > 0), '#home:gallery', 'no_consented_student_work', 'share_student_work', {
          surface: 'home', placement: 'after_courses', publishedVersion,
        }),
      faq: entry('faq', bool(website.show_faq ?? website.showFaq, true), faqItems.length > 0,
        '#home:faq', 'no_faq_content', 'add_faq', { surface: 'home', placement: 'after_gallery', publishedVersion }),
      contact: entry('contact', bool(website.show_contact ?? website.showContact, true), contactReady,
        '#home:contact', 'missing_contact_details', 'add_contact_details', {
          surface: 'home', placement: 'after_faq', navigationEligible: false, footerEligible: false, publishedVersion,
        }),
      student: entry('student', studentIntent, true, '#my', '', '', {
        surface: 'home', placement: 'utility', publishedVersion,
      }),
      register: entry('register', true, Boolean(Object.keys(registration).length || brand.name),
        '#join', 'registration_unavailable', 'complete_registration_profile', {
          surface: 'register', placement: 'action', publishedVersion,
        }),
    };
    const navigation = Object.values(modules).filter((module) => module.navigationEligible);
    const footer = Object.values(modules).filter((module) => module.footerEligible);
    return { version: 2, generatedAt: new Date().toISOString(), publishedVersion,
      modules, navigation, footer, actions: actionsFor(hero, modules) };
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
    const secondary = contract.actions?.secondary;
    const secondaryNode = scope.getElementById ? scope.getElementById('heroSecondaryCta') : null;
    if (secondaryNode) {
      secondaryNode.style.display = secondary?.visible ? '' : 'none';
      secondaryNode.setAttribute('aria-hidden', secondary?.visible ? 'false' : 'true');
      if (secondary?.visible) {
        secondaryNode.href = secondary.href;
        secondaryNode.dataset.analyticsLabel = `hero_${secondary.targetType}`;
        secondaryNode.removeAttribute('tabindex');
      } else {
        secondaryNode.setAttribute('tabindex', '-1');
      }
    }
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
