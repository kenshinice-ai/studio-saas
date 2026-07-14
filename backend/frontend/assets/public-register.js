(function () {
  function text(value) {
    return String(value == null ? '' : value).trim();
  }

  function localized(field, baseKey, language) {
    var preferred = text(field[baseKey + '_' + language]);
    return preferred || text(field[baseKey]) || text(field[baseKey + '_en']) || text(field[baseKey + '_zh']);
  }

  function normalizeProfile(profile, fallbackTitle, language) {
    var raw = profile && typeof profile === 'object' ? profile : {};
    var fields = Array.isArray(raw.fields) ? raw.fields : [];
    var lang = language === 'en' ? 'en' : 'zh';
    return {
      title: text(raw.title) || fallbackTitle || 'Student Registration',
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
    if (!container) return normalizeProfile(profile, opts.fallbackTitle, opts.language);
    var normalized = normalizeProfile(profile, opts.fallbackTitle, opts.language);
    container.innerHTML = '';
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
      wrap.appendChild(caption);
      wrap.appendChild(input);
      container.appendChild(wrap);
    });
    return normalized;
  }

  function collectFields(options) {
    var opts = options || {};
    var container = typeof opts.container === 'string' ? document.getElementById(opts.container) : opts.container;
    if (!container) return [];
    return Array.from(container.querySelectorAll('[data-profile-key]')).map(function (input) {
      var value = text(input.value);
      var fieldWrap = input.closest(opts.labelSelector || '.dyn-field') || input.parentElement;
      var labelNode = fieldWrap ? fieldWrap.querySelector('label') : null;
      var label = labelNode ? text(labelNode.textContent).replace(/\s+\*$/, '') : text(input.dataset.profileKey);
      if (input.required && !value) {
        throw new Error((opts.requiredPrefix || 'Please complete') + ' ' + label + '.');
      }
      return value ? label + ': ' + value : '';
    }).filter(Boolean);
  }

  window.StudioSaaSPublicRegister = {
    normalizeProfile: normalizeProfile,
    renderFields: renderFields,
    collectFields: collectFields
  };
})();
