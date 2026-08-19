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

  function mount(config) {
    const originalText = new WeakMap();
    const renderedText = new WeakMap();
    const originalAttributes = new WeakMap();
    let language = localStorage.getItem(STORAGE_KEY) === 'en' ? 'en' : 'zh';
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

    function setLanguage(next) {
      language = next === 'en' ? 'en' : 'zh';
      /* One key across the CMS and both consoles: one choice covers the day. */
      localStorage.setItem(STORAGE_KEY, language);
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
          if (button) setLanguage(button.getAttribute(dataAttr));
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
