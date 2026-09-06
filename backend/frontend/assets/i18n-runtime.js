/* Shared i18n runtime for the CMS and the two consoles.
 *
 * v10.11.0: cms-i18n.js and admin-i18n.js each carried a full copy of the same
 * engine — dictionary lookup, whole-sentence rule rendering, and a
 * MutationObserver that re-localises text AND the three localised attributes
 * (placeholder / title / aria-label) as the page rewrites them. The two copies
 * drifted, and the same three defect classes were fixed twice (duplicate keys,
 * an observer that ignored attributes, fragment phrases). This file is the one
 * engine; the surface files keep what is genuinely theirs: the dictionary, the
 * sentence rules, and surface policy hooks.
 *
 * Fail-open by contract: this layer is cosmetic. If anything in here throws,
 * the page must keep working in its source language — so every entry point is
 * wrapped, and failures are LOUD in the console rather than silent. (The
 * "silent fallbacks are the defect" rule is about money and permission paths
 * swallowing errors; an observable cosmetic degrade is the opposite of that.)
 *
 * mount(config) fields:
 *   globalName          window.<name> API: {language, setLanguage, translate, localise}
 *   targetLanguage      the language translate() produces ('en' for the CMS,
 *                       'zh' for the consoles — their source strings differ)
 *   translateCore(s)    dictionary + sentence rules; returns s when unlisted
 *                       (a missing translation should read oddly, not disappear)
 *   prefix              data-attribute base: 'cms-language' → data-cms-language,
 *                       data-cms-language-switch
 *   switchClass         class for the injected switch holder
 *   switchButtons       [['zh','中'],['en','EN']] — value/label pairs
 *   placeSwitch(el)     where the switch mounts (body corner vs header)
 *   ignoreSelector      extra containers whose text keeps its own language
 *   attrKeepsOwnLanguage(element, attr)   surface policy (the consoles' `*En`
 *                       placeholder lock); optional
 *   styleText           the switch's CSS (theme-token colours, surface-specific)
 *   wrapNativeDialogs   translate alert/confirm/prompt messages (consoles)
 *   eventName           CustomEvent dispatched on language change
 */
(function () {
  'use strict';

  const STORAGE_KEY = 'studiosaas_admin_language';
  /* 「用户选过」和「默认写进去的」必须分开存。
     STORAGE_KEY 一直同时承担两件事：mount() 结尾无条件调 setLanguage(language)，
     所以第一次打开控制台就把默认值写了进去。实测（生产，2026-09-06）：清空这个
     键、用 navigator.languages 为 ["en-GB","en-US","en"] 的浏览器重新加载，它自己
     写回了 "zh"。
     后果是：如果三级回退只读这个键，凡是打开过控制台的人本地都已经有值，
     升级之后会「毫无变化」——这一条修了等于没修。
     所以选择记在 CHOICE_KEY 里，只由 setLanguage() 写；STORAGE_KEY 继续跟着
     生效语言走，因为别处（成长报告等）在读它。
     迁移：旧键里的 'en' 只可能来自一次显式选择——默认值从来不写 'en'，
     所以它是可信的。旧键里的 'zh' 无从分辨，忽略它，让浏览器语言说话。 */
  const CHOICE_KEY = 'studiosaas_admin_language_choice';

  function normaliseLanguage(value) {
    const text = String(value || '').toLowerCase();
    if (text.indexOf('en') === 0) return 'en';
    if (text.indexOf('zh') === 0) return 'zh';
    return '';
  }

  /* 三级：用户选过的 → 浏览器支持的 → 项目默认。
     和租户门户用的是同一套顺序（tenant-template/index.html 的 LANG），
     只是门户多一个可分享的 ?lang= 前缀。 */
  function resolveLanguage() {
    try {
      const chosen = normaliseLanguage(localStorage.getItem(CHOICE_KEY));
      if (chosen) return chosen;
      if (normaliseLanguage(localStorage.getItem(STORAGE_KEY)) === 'en') return 'en';
    } catch (error) { /* 隐私模式下读不到 storage：往下走浏览器语言 */ }
    try {
      const browser = normaliseLanguage(
        (navigator.languages && navigator.languages[0]) || navigator.language);
      if (browser) return browser;
    } catch (error) { /* 同上 */ }
    return 'zh';
  }

  function mount(config) {
    const originalText = new WeakMap();
    const renderedText = new WeakMap();
    const originalAttributes = new WeakMap();
    let language = resolveLanguage();
    let observer;

    const target = config.targetLanguage;
    const dataAttr = `data-${config.prefix}`;
    const switchSelector = `[data-${config.prefix}-switch]`;
    const ignoreSelector = config.ignoreSelector
      ? `${switchSelector},${config.ignoreSelector}` : switchSelector;
    const attrKeepsOwnLanguage = config.attrKeepsOwnLanguage || (() => false);

    function translate(value) {
      const clean = String(value == null ? '' : value).replace(/\s+/g, ' ').trim();
      if (!clean || language !== target) return clean;
      return config.translateCore(clean);
    }

    function isIgnored(node) {
      return !node.parentElement
        || /^(SCRIPT|STYLE|CODE|PRE|TEXTAREA)$/.test(node.parentElement.tagName)
        || Boolean(node.parentElement.closest(ignoreSelector));
    }

    function applyText(node) {
      if (isIgnored(node)) return;
      const current = node.nodeValue;
      if (!originalText.has(node) || (renderedText.has(node) && current !== renderedText.get(node))) {
        originalText.set(node, current);
      }
      const source = originalText.get(node);
      const clean = String(source).replace(/\s+/g, ' ').trim();
      const leading = (String(source).match(/^\s*/) || [''])[0];
      const trailing = (String(source).match(/\s*$/) || [''])[0];
      const next = language === target && clean ? `${leading}${translate(clean)}${trailing}` : source;
      if (current !== next) {
        renderedText.set(node, next);
        node.nodeValue = next;
      } else {
        renderedText.set(node, current);
      }
    }

    function applyAttributes(element) {
      if (!originalAttributes.has(element)) originalAttributes.set(element, {});
      const originals = originalAttributes.get(element);
      for (const attr of ['placeholder', 'title', 'aria-label']) {
        if (!element.hasAttribute(attr)) continue;
        if (attrKeepsOwnLanguage(element, attr)) continue;
        const key = `i18nRendered${attr.replace('-', '')}`;
        const current = element.getAttribute(attr);
        if (!(attr in originals) || current !== (element.dataset[key] || originals[attr])) originals[attr] = current;
        const next = language === target ? translate(originals[attr]) : originals[attr];
        if (current !== next) element.setAttribute(attr, next);
        element.dataset[key] = next;
      }
    }

    function localise(root) {
      if (!root) return;
      if (root.nodeType === Node.TEXT_NODE) return applyText(root);
      if (![Node.ELEMENT_NODE, Node.DOCUMENT_NODE, Node.DOCUMENT_FRAGMENT_NODE].includes(root.nodeType)) return;
      if (root.nodeType === Node.ELEMENT_NODE) applyAttributes(root);
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      let node;
      while ((node = walker.nextNode())) applyText(node);
      if (root.querySelectorAll) root.querySelectorAll('[placeholder],[title],[aria-label]').forEach(applyAttributes);
    }

    function updateSwitch() {
      document.querySelectorAll(`[${dataAttr}]`).forEach((button) => {
        const active = button.getAttribute(dataAttr) === language;
        button.classList.toggle('active', active);
        button.setAttribute('aria-pressed', String(active));
      });
    }

    function setLanguage(next, fromUser = false) {
      language = next === 'en' ? 'en' : 'zh';
      /* One key across the CMS and both consoles: one choice covers the day.
         STORAGE_KEY 跟着生效语言走（别处在读它）；CHOICE_KEY 只在这是一次
         用户操作时写——否则默认值又会把自己伪装成一次选择，而那正是这一条
         缺陷第一次出现的方式。 */
      try {
        localStorage.setItem(STORAGE_KEY, language);
        if (fromUser) localStorage.setItem(CHOICE_KEY, language);
      } catch (error) { /* 隐私模式：这一次会话内仍然有效 */ }
      document.documentElement.lang = language === 'zh' ? 'zh-CN' : 'en';
      localise(document);
      updateSwitch();
      document.dispatchEvent(new CustomEvent(config.eventName, { detail: { language } }));
    }

    function installSwitch() {
      if (document.querySelector(switchSelector)) return;
      const holder = document.createElement('div');
      holder.setAttribute(`data-${config.prefix}-switch`, '');
      holder.className = config.switchClass;
      holder.setAttribute('role', 'group');
      holder.setAttribute('aria-label', 'Language / 语言');
      holder.innerHTML = config.switchButtons
        .map(([value, label]) => `<button type="button" ${dataAttr}="${value}">${label}</button>`)
        .join('');
      config.placeSwitch(holder);
      holder.addEventListener('click', (event) => {
        try {
          const button = event.target.closest(`[${dataAttr}]`);
          if (button) setLanguage(button.getAttribute(dataAttr), true);
        } catch (error) {
          console.error('[i18n-runtime] language switch failed:', error);
        }
      });
      updateSwitch();
    }

    function installStyles() {
      const style = document.createElement('style');
      style.textContent = config.styleText;
      document.head.appendChild(style);
    }

    function wrapDialogs() {
      const nativeAlert = window.alert.bind(window);
      const nativeConfirm = window.confirm.bind(window);
      const nativePrompt = window.prompt.bind(window);
      window.alert = (message) => nativeAlert(language === target ? translate(message) : message);
      window.confirm = (message) => nativeConfirm(language === target ? translate(message) : message);
      window.prompt = (message, value) => nativePrompt(language === target ? translate(message) : message, value);
    }

    function start() {
      installStyles();
      installSwitch();
      if (config.wrapNativeDialogs) wrapDialogs();
      setLanguage(language);
      observer = new MutationObserver((mutations) => {
        try {
          for (const mutation of mutations) {
            if (mutation.type === 'characterData') {
              if (renderedText.get(mutation.target) === mutation.target.nodeValue) continue;
              applyText(mutation.target);
            }
            /* A mounted element keeps its identity while the page rewrites its
             * label. Without this branch attribute values were localised once,
             * at insertion, and every later rewrite kept the source language. */
            if (mutation.type === 'attributes') applyAttributes(mutation.target);
            mutation.addedNodes.forEach(localise);
          }
          updateSwitch();
        } catch (error) {
          console.error('[i18n-runtime] observer pass failed; page stays readable in its source language:', error);
        }
      });
      observer.observe(document.body, {
        subtree: true, childList: true, characterData: true,
        /* Filtered on purpose: applyAttributes stamps its result in a data-
         * attribute, and an unfiltered watch would call itself back forever. */
        attributes: true, attributeFilter: ['placeholder', 'title', 'aria-label'],
      });
    }

    window[config.globalName] = {
      get language() { return language; },
      setLanguage,
      translate: (value) => (language === target ? translate(value) : value),
      localise,
    };

    function safeStart() {
      try {
        start();
      } catch (error) {
        console.error('[i18n-runtime] failed to start; page stays in its source language:', error);
      }
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', safeStart, { once: true });
    else safeStart();
  }

  window.StudioI18n = { mount };
})();
