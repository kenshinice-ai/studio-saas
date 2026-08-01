(function () {
  function text(value) {
    return String(value == null ? '' : value).trim();
  }

  function localized(field, baseKey, language) {
    var preferred = text(field[baseKey + '_' + language]);
    return preferred || text(field[baseKey]) || text(field[baseKey + '_en']) || text(field[baseKey + '_zh']);
  }

  /* Batch 5: the profile title is a {zh, en} pair now. Bare strings still arrive
     from tenants saved before that, and are used for whichever language asks. */
  function pair(value, language) {
    if (value && typeof value === 'object') {
      return text(value[language]) || text(value.zh) || text(value.en);
    }
    return text(value);
  }

  function normalizeProfile(profile, fallbackTitle, language) {
    var raw = profile && typeof profile === 'object' ? profile : {};
    var fields = Array.isArray(raw.fields) ? raw.fields : [];
    var lang = language === 'en' ? 'en' : 'zh';
    return {
      title: pair(raw.title, lang) || fallbackTitle || 'Student Registration',
      fields: fields.slice(0, 8).filter(function (field) {
        return field && text(field.key) && localized(field, 'label', lang);
      }).map(function (field) {
        return {
          key: text(field.key),
          label: localized(field, 'label', lang),
          label_en: localized(field, 'label', 'en'),
          label_zh: localized(field, 'label', 'zh'),
          placeholder: localized(field, 'placeholder', lang),
          placeholder_en: localized(field, 'placeholder', 'en'),
          placeholder_zh: localized(field, 'placeholder', 'zh'),
          type: text(field.type || 'text'),
          options: Array.isArray(field.options) ? field.options.map(text).filter(Boolean) : [],
          required: Boolean(field.required)
        };
      })
    };
  }

  function renderFields(profile, options) {
    var opts = options || {};
    var container = typeof opts.container === 'string' ? document.getElementById(opts.container) : opts.container;
    var requiredContainer = typeof opts.requiredContainer === 'string'
      ? document.getElementById(opts.requiredContainer) : opts.requiredContainer;
    var optionalContainer = typeof opts.optionalContainer === 'string'
      ? document.getElementById(opts.optionalContainer) : opts.optionalContainer;
    if (!container && !requiredContainer && !optionalContainer) {
      return normalizeProfile(profile, opts.fallbackTitle, opts.language);
    }
    var normalized = normalizeProfile(profile, opts.fallbackTitle, opts.language);
    /* Switching language re-renders these inputs. Without this, a visitor who
     * hit EN halfway through lost everything they had typed into the custom
     * fields, because renderFields() wipes the container. */
    var previous = {};
    if (opts.preserveValues) {
      [container, requiredContainer, optionalContainer].filter(Boolean).forEach(function (mount) {
        Array.prototype.forEach.call(mount.querySelectorAll('[data-profile-key]'), function (input) {
          if (input.value) previous[input.dataset.profileKey] = input.value;
        });
      });
    }
    [container, requiredContainer, optionalContainer].filter(Boolean).forEach(function (mount, index, mounts) {
      if (mounts.indexOf(mount) === index) mount.innerHTML = '';
    });
    normalized.fields.forEach(function (field) {
      var wrap = document.createElement('div');
      wrap.className = opts.labelClass || 'dyn-field';
        var caption = document.createElement('label');
        caption.textContent = field.label + (field.required ? ' *' : '');
      var input;
      if (field.type === 'textarea' || opts.multiline) {
        input = document.createElement('textarea');
        input.rows = opts.rows || 2;
      } else if (field.type === 'select') {
        input = document.createElement('select');
        var blank = document.createElement('option');
        blank.value = '';
        blank.textContent = field.placeholder || (opts.language === 'zh' ? '请选择…' : 'Please choose...');
        input.appendChild(blank);
        field.options.forEach(function (option) {
          var opt = document.createElement('option');
          opt.value = option;
          opt.textContent = option;
          input.appendChild(opt);
        });
      } else {
        input = document.createElement('input');
      }
      input.dataset.profileKey = field.key;
      input.id = 'profile-' + field.key.replace(/[^a-zA-Z0-9_-]/g, '-');
      caption.htmlFor = input.id;
      input.placeholder = field.placeholder || field.label;
      input.required = field.required;
      if (field.required) input.setAttribute('aria-required', 'true');
      if (opts.inputClass) input.className = opts.inputClass;
      if (Object.prototype.hasOwnProperty.call(previous, field.key)) input.value = previous[field.key];
      wrap.appendChild(caption);
      wrap.appendChild(input);
      /* A required custom field carries the same per-field error note the
       * built-in fields have, so failFirst/markFieldError can show it and
       * point aria-describedby at it. */
      if (field.required) {
        var note = document.createElement('span');
        note.className = opts.errorClass || 'field-error';
        note.id = input.id + '-err';
        note.textContent = opts.language === 'en'
          ? 'Please complete ' + field.label + '.'
          : '请填写' + field.label;
        wrap.appendChild(note);
      }
      var mount = field.required
        ? (requiredContainer || container || optionalContainer)
        : (optionalContainer || container || requiredContainer);
      mount.appendChild(wrap);
    });
    return normalized;
  }

  /* P2-8 (custom fields): this used to throw on the first missing required
   * field, which bypassed the callers' failFirst path — one global sentence,
   * no aria-invalid, no focus move. It now reports every failure so the
   * callers can mark the fields exactly like the built-in ones. */
  function collectFields(options) {
    var opts = options || {};
    var container = typeof opts.container === 'string' ? document.getElementById(opts.container) : opts.container;
    var containers = Array.isArray(opts.containers)
      ? opts.containers.map(function (item) {
          return typeof item === 'string' ? document.getElementById(item) : item;
        }).filter(Boolean)
      : [container].filter(Boolean);
    if (!containers.length) return { values: [], missing: [] };
    var values = [];
    var missing = [];
    var inputs = [];
    containers.forEach(function (mount) {
      inputs = inputs.concat(Array.from(mount.querySelectorAll('[data-profile-key]')));
    });
    inputs.forEach(function (input) {
      var value = text(input.value);
      var fieldWrap = input.closest(opts.labelSelector || '.dyn-field') || input.parentElement;
      var labelNode = fieldWrap ? fieldWrap.querySelector('label') : null;
      var label = labelNode ? text(labelNode.textContent).replace(/\s+\*$/, '') : text(input.dataset.profileKey);
      if (input.required && !value) missing.push({ el: input, label: label });
      else if (value) values.push(label + ': ' + value);
    });
    return { values: values, missing: missing };
  }

  /* One submit path for both public registration surfaces.
   *
   * The portal and the standalone register page each had their own POST, and
   * they had already drifted: different success copy, different `source`
   * values, and privacyNoticeVersion hard-coded separately in two files — which
   * meant a consent record could cite a notice version the other page never
   * used. Callers now pass only what genuinely differs (`source`) and the
   * privacy notice version they were told to record by /brand.
   */
  var PUBLICATION_NOTICE_VERSION = '2026-07-18';

  function submit(options) {
    var opts = options || {};
    var values = opts.values || {};
    var campaign = {};
    try {
      var params = new URLSearchParams(location.search);
      ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term'].forEach(function (key) {
        if (params.get(key)) campaign[key] = params.get(key);
      });
    } catch (_) { /* no query string is fine */ }

    var body = {
      firstName: text(values.firstName),
      lastName: text(values.lastName),
      mobile: text(values.mobile),
      email: text(values.email),
      message: text(values.message),
      website: text(values.website),
      source: opts.source || 'portal',
      sourcePath: location.pathname,
      language: opts.language === 'en' ? 'en' : 'zh',
      privacyConsent: true,
      privacyNoticeVersion: opts.privacyNoticeVersion || '2026-07-12'
    };
    if (opts.publicationConsent) {
      body.publicationConsent = {
        confirmed: true,
        consentBy: text(opts.publicationConsent.consentBy),
        relationship: text(opts.publicationConsent.relationship),
        method: opts.publicationConsent.method || 'registration_form',
        noticeVersion: opts.publicationConsent.noticeVersion || PUBLICATION_NOTICE_VERSION
      };
    }
    Object.keys(campaign).forEach(function (key) { body[key] = campaign[key]; });

    // B4: name the cause and the way out. "Submission failed" alone leaves the
    // visitor guessing whether to retry, fix a field, or phone the studio.
    var fallback = body.language === 'en'
      ? 'The studio could not accept this registration. Check the phone number and try once more — if it keeps failing, call the studio and they can add you by hand.'
      : '工作室没能接收这份报名。请检查手机号后再提交一次；如果仍然失败，直接致电工作室，他们可以帮你手动登记。';
    var networkError = body.language === 'en'
      ? 'Could not reach the studio — your connection dropped. Your details are still filled in, so just tap submit again.'
      : '连接不上工作室，可能是网络中断。你填的内容都还在，重新点一次提交即可。';

    return fetch('/v1/public/' + encodeURIComponent(opts.slug) + '/registrations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    }).catch(function () {
      throw new Error(networkError);
    }).then(function (response) {
      return response.json().catch(function () { return {}; }).then(function (data) {
        if (!response.ok || !data.success) throw new Error(data.message || data.error || fallback);
        return data;
      });
    });
  }

  window.StudioSaaSPublicRegister = {
    normalizeProfile: normalizeProfile,
    renderFields: renderFields,
    collectFields: collectFields,
    submit: submit
  };
})();
