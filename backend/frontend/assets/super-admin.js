/* Super Admin console script — externalised verbatim from
 * super-admin.html in v10.11.0. Deliberately self-contained and NOT
 * shared with the tenant-facing consoles: this is the rescue surface,
 * and the rescue tool does not ride in the same boat as what it
 * rescues. Classic script; top-level declarations stay global.
 */
    const $ = (id) => document.getElementById(id);
    let tenants = [];
    let plans = [];
    let settlement = null;   // the subscription-date report, loaded with the rest
    let auditLogs = [];
    let editingTenantId = '';
    let editingPlanCode = '';
    let selectedTenantId = '';
    let tenantPage = 0;
    let metricFilter = '';
    const tenantPageSize = 10;
    let auditPage = 0;
    const auditPageSize = 15;
    let isLoading = false;
    let currentUser = null;
    const WORKSPACE_LABELS = {
      overview: 'Overview',
      tenants: 'Tenants',
      plans: 'Plans',
      audit: 'Audit Logs'
    };
    const WORKSPACE_IDS = new Set(Object.keys(WORKSPACE_LABELS));
    let activeWorkspace = 'overview';
    let lastRefreshAt = null;
    let workspaceFailures = [];
    let workspaceLoadError = false;
    let navLinks = [];
    let setActiveNav = () => {};
    let inspectorMode = 'workspace';
    let inspectorSelection = null;
    let workspaceEditorKind = '';
    let workspaceEditorId = '';
    let workspaceEditorReturnFocus = null;
    let workspaceEditorDirty = false;
    let mobileNavOpen = false;
    let activeActionMenu = null;
    let actionMenuReturnFocus = null;
    let inspectorActionKey = '';
    let workspaceEditorFocusSection = '';

    function setMobileNavOpen(open) {
      mobileNavOpen = Boolean(open);
      const rail = $('platformRail');
      const toggle = $('platformMobileNavToggle');
      const scrim = $('platformMobileNavScrim');
      rail?.classList.toggle('is-mobile-open', mobileNavOpen);
      if (toggle) {
        toggle.setAttribute('aria-expanded', String(mobileNavOpen));
        const label = toggle.querySelector('span');
        if (label) setWorkspaceText(label, mobileNavOpen ? 'Close work areas' : 'Work areas');
      }
      if (scrim) scrim.hidden = !mobileNavOpen;
    }

    function workspaceFromHash() {
      const candidate = String(window.location.hash || '').replace(/^#/, '');
      return WORKSPACE_IDS.has(candidate) ? candidate : 'overview';
    }

    function isWorkspaceEditorOpen() {
      return Boolean($('platformEditWorkspace') && !$('platformEditWorkspace').hidden);
    }

    function setWorkspaceEditorState(value, dirty = workspaceEditorDirty) {
      const editor = $('platformEditWorkspace');
      const state = $('workspaceEditorState');
      if (state) setWorkspaceText(state, value);
      editor?.classList.toggle('is-dirty', dirty);
    }

    function markWorkspaceEditorDirty() {
      workspaceEditorDirty = true;
      setWorkspaceEditorState('Unsaved changes', true);
      renderEditorInspector();
    }

    function workspaceEditorRoot() {
      return isWorkspaceEditorOpen() ? $('platformEditWorkspace') : $('modalOverlay');
    }

    function openWorkspaceEditor({ workspace, kind, id = '', title, subtitle, bodyHtml, footerHtml }) {
      if (isWorkspaceEditorOpen() && workspaceEditorDirty && !window.confirm('Discard unsaved changes?')) return false;
      if ($('modalOverlay')?.classList.contains('active')) closeModal();
      workspaceEditorReturnFocus = document.activeElement;
      activeWorkspace = WORKSPACE_IDS.has(workspace) ? workspace : activeWorkspace;
      workspaceEditorKind = kind;
      workspaceEditorId = id;
      workspaceEditorDirty = false;
      setActiveNav(`#${activeWorkspace}`);
      document.querySelectorAll('[data-workspace]').forEach((section) => {
        section.hidden = true;
        section.setAttribute('aria-hidden', 'true');
      });
      const editor = $('platformEditWorkspace');
      if (!editor) return false;
      editor.hidden = false;
      $('workspaceEditorKicker').textContent = kind === 'tenant' ? 'Tenant workspace' : 'Plan workspace';
      $('workspaceEditorTitle').textContent = title;
      $('workspaceEditorSubtitle').textContent = subtitle;
      $('workspaceEditorBody').innerHTML = bodyHtml;
      $('workspaceEditorFooter').innerHTML = footerHtml;
      setWorkspaceEditorState('Ready', false);
      editor.querySelectorAll('input, select, textarea').forEach((field) => {
        field.addEventListener('input', markWorkspaceEditorDirty);
        field.addEventListener('change', markWorkspaceEditorDirty);
      });
      renderEditorInspector();
      const focusTarget = $('workspaceEditorBody').querySelector('input:not([disabled]), select, textarea, button') || $('workspaceEditorFooter').querySelector('button');
      if (focusTarget) focusTarget.focus();
      return true;
    }

    function closeWorkspaceEditor({ confirm = true, focus = true } = {}) {
      if (!isWorkspaceEditorOpen()) return true;
      if (confirm && workspaceEditorDirty && !window.confirm('Discard unsaved changes?')) return false;
      const editor = $('platformEditWorkspace');
      editor.hidden = true;
      editor.classList.remove('is-dirty', 'is-submitting');
      $('workspaceEditorBody').replaceChildren();
      $('workspaceEditorFooter').replaceChildren();
      workspaceEditorKind = '';
      workspaceEditorId = '';
      workspaceEditorFocusSection = '';
      workspaceEditorDirty = false;
      const activeSection = document.querySelector(`[data-workspace="${activeWorkspace}"]`);
      if (activeSection) {
        activeSection.hidden = false;
        activeSection.setAttribute('aria-hidden', 'false');
      }
      rerenderInspector();
      if (focus && workspaceEditorReturnFocus && typeof workspaceEditorReturnFocus.focus === 'function') workspaceEditorReturnFocus.focus();
      workspaceEditorReturnFocus = null;
      return true;
    }

    function closeActiveEditor() {
      return closeWorkspaceEditor({ confirm: false });
    }

    function setWorkspaceText(element, value) {
      if (!element) return;
      element.textContent = value;
      window.AdminI18n?.localise?.(element);
    }

    function updateWorkspaceHeaderOffset() {
      const header = document.querySelector('.header');
      if (!header) return;
      document.documentElement.style.setProperty('--workspace-header-offset', `${Math.ceil(header.getBoundingClientRect().height)}px`);
    }

    function renderWorkspaceContext() {
      const context = $('workspaceContext');
      if (!context) return;
      const state = !currentUser ? 'Not refreshed' : isLoading ? 'Loading' : workspaceLoadError ? 'Error' : workspaceFailures.length ? 'Partial load' : lastRefreshAt ? 'Ready' : 'Not refreshed';
      const stateClass = state === 'Loading' ? 'is-loading' : state === 'Partial load' ? 'is-partial' : state === 'Error' ? 'is-error' : '';
      context.classList.remove('is-loading', 'is-partial', 'is-error');
      if (stateClass) context.classList.add(stateClass);
      setWorkspaceText($('workspaceContextTitle'), WORKSPACE_LABELS[activeWorkspace]);
      setWorkspaceText($('workspaceDataState'), state);
      setWorkspaceText($('lastRefreshLabel'), lastRefreshAt ? `Last refreshed: ${formatTimestamp(lastRefreshAt.toISOString())}` : 'Not refreshed');
      const retry = $('workspaceRetryBtn');
      if (retry) {
        retry.hidden = !currentUser || isLoading || !workspaceFailures.length;
        window.AdminI18n?.localise?.(retry);
      }
    }

    function inspectorText(value, fallback = '—') {
      return value === null || value === undefined || value === '' ? fallback : text(value);
    }

    function setInspectorHeader(kicker, title) {
      relabel($('workspaceInspectorKicker'), kicker);
      relabel($('workspaceInspectorTitle'), title);
    }

    function inspectorSection(title, subtitle = '') {
      const section = document.createElement('section');
      section.className = 'inspector-section';
      const heading = document.createElement('div');
      heading.className = 'inspector-section-title';
      const titleEl = document.createElement('span');
      relabel(titleEl, title);
      heading.appendChild(titleEl);
      if (subtitle) {
        const subtitleEl = document.createElement('small');
        relabel(subtitleEl, subtitle);
        heading.appendChild(subtitleEl);
      }
      section.appendChild(heading);
      return section;
    }

    function inspectorMeta(parent, label, value) {
      const row = document.createElement('div');
      row.className = 'inspector-meta-row';
      const labelEl = document.createElement('span');
      relabel(labelEl, label);
      const valueEl = document.createElement('strong');
      valueEl.className = 'tabular';
      valueEl.textContent = inspectorText(value);
      row.append(labelEl, valueEl);
      parent.appendChild(row);
      return row;
    }

    function inspectorAction(parent, label, handler, className = 'inspector-action') {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = className;
      const labelEl = document.createElement('span');
      relabel(labelEl, label);
      const arrow = document.createElement('span');
      arrow.textContent = '→';
      arrow.setAttribute('aria-hidden', 'true');
      button.append(labelEl, arrow);
      button.addEventListener('click', handler);
      parent.appendChild(button);
      return button;
    }

    function closeActionMenu({ restoreFocus = true } = {}) {
      if (!activeActionMenu) return;
      activeActionMenu.backdrop?.remove();
      activeActionMenu.popover?.remove();
      activeActionMenu = null;
      const focusTarget = actionMenuReturnFocus;
      actionMenuReturnFocus = null;
      if (restoreFocus && focusTarget && typeof focusTarget.focus === 'function') focusTarget.focus();
    }

    function actionMenuItem(parent, label, handler, { danger = false, disabled = false } = {}) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = `action-menu-item${danger ? ' danger' : ''}`;
      button.disabled = Boolean(disabled);
      button.setAttribute('role', 'menuitem');
      const copy = document.createElement('span');
      relabel(copy, label);
      const arrow = document.createElement('span');
      arrow.className = 'action-menu-arrow';
      arrow.textContent = '→';
      arrow.setAttribute('aria-hidden', 'true');
      button.append(copy, arrow);
      button.addEventListener('click', () => {
        if (button.disabled) return;
        closeActionMenu({ restoreFocus: false });
        handler(button);
      });
      parent.appendChild(button);
      return button;
    }

    function openActionMenu({ title, subtitle = '', anchor = null, groups = [] } = {}) {
      closeActionMenu({ restoreFocus: false });
      actionMenuReturnFocus = anchor || document.activeElement;
      const backdrop = document.createElement('div');
      backdrop.className = 'action-menu-backdrop';
      backdrop.setAttribute('aria-hidden', 'true');
      backdrop.addEventListener('click', () => closeActionMenu());
      const popover = document.createElement('div');
      popover.className = 'action-menu-popover';
      popover.setAttribute('role', 'menu');
      popover.setAttribute('aria-label', String(title || 'Actions'));
      const header = document.createElement('div');
      header.className = 'action-menu-header';
      const titleEl = document.createElement('strong');
      titleEl.className = 'action-menu-title';
      relabel(titleEl, title || 'Actions');
      header.appendChild(titleEl);
      if (subtitle) {
        const subtitleEl = document.createElement('span');
        subtitleEl.className = 'action-menu-subtitle';
        relabel(subtitleEl, subtitle);
        header.appendChild(subtitleEl);
      }
      popover.appendChild(header);
      groups.forEach(({ title: groupTitle, items = [] }) => {
        const group = document.createElement('section');
        group.className = 'action-menu-group';
        const heading = document.createElement('div');
        heading.className = 'action-menu-group-title';
        relabel(heading, groupTitle);
        group.appendChild(heading);
        items.forEach((item) => actionMenuItem(group, item.label, item.handler, item));
        popover.appendChild(group);
      });
      document.body.append(backdrop, popover);
      activeActionMenu = { backdrop, popover };
      const place = () => {
        if (!anchor || window.matchMedia('(max-width: 767px)').matches) return;
        const rect = anchor.getBoundingClientRect();
        const width = popover.offsetWidth;
        const height = popover.offsetHeight;
        const gap = 6;
        const left = Math.max(12, Math.min(rect.right - width, window.innerWidth - width - 12));
        const below = rect.bottom + gap;
        const top = below + height <= window.innerHeight - 12
          ? below
          : Math.max(12, rect.top - height - gap);
        popover.style.left = `${Math.round(left)}px`;
        popover.style.top = `${Math.round(top)}px`;
      };
      requestAnimationFrame(place);
      const first = popover.querySelector('[role="menuitem"]:not(:disabled)');
      if (first) first.focus();
      window.AdminI18n?.localise?.(popover);
    }

    function openInspector() {
      const inspector = $('workspaceInspector');
      const shell = $('platformWorkspaceShell');
      if (!inspector || !shell) return;
      inspector.hidden = false;
      inspector.classList.add('is-open');
      shell.classList.remove('inspector-closed');
    }

    function closeInspector() {
      setMobileNavOpen(false);
      closeActionMenu({ restoreFocus: false });
      selectedTenantId = '';
      inspectorMode = 'workspace';
      inspectorSelection = null;
      inspectorActionKey = '';
      const inspector = $('workspaceInspector');
      const shell = $('platformWorkspaceShell');
      document.querySelectorAll('tr.is-inspector-selected').forEach((row) => row.classList.remove('is-inspector-selected'));
      if (inspector) {
        inspector.classList.remove('is-open');
        inspector.hidden = true;
      }
      if (shell) shell.classList.add('inspector-closed');
    }

    function renderWorkspaceInspector() {
      const body = $('workspaceInspectorBody');
      if (!body) return;
      inspectorMode = 'workspace';
      inspectorSelection = null;
      setInspectorHeader('Workspace context', WORKSPACE_LABELS[activeWorkspace]);
      body.replaceChildren();
      const intro = document.createElement('div');
      intro.className = 'inspector-placeholder';
      const strong = document.createElement('strong');
      relabel(strong, activeWorkspace === 'overview' ? 'Start with what needs attention.' : 'Select a row to inspect its context.');
      const copy = document.createElement('span');
      const copyByWorkspace = {
        overview: 'The workspace prioritises subscription risk, usage signals, and operator follow-up.',
        tenants: 'Choose a tenant to review status, subscription metadata, resource usage, and safe next actions.',
        plans: 'Choose a plan to review its commercial limits and publication state.',
        audit: 'Choose an event to inspect the actor, resource, reason, and captured metadata.'
      };
      relabel(copy, copyByWorkspace[activeWorkspace]);
      intro.append(strong, copy);
      body.appendChild(intro);
      const section = inspectorSection('Current area', 'Decision guide');
      inspectorMeta(section, 'Workspace', WORKSPACE_LABELS[activeWorkspace]);
      inspectorMeta(section, 'Data state', $('workspaceDataState')?.textContent || 'Not refreshed');
      inspectorMeta(section, 'Attention items', $('attentionCountBadge')?.textContent || '0');
      body.appendChild(section);
      /* On a phone an empty inspector must not sit above the table and steal
         the first row's operation target. It opens again when a row or action
         context is selected. */
      if (window.matchMedia('(max-width: 767px)').matches) {
        const inspector = $('workspaceInspector');
        const shell = $('platformWorkspaceShell');
        inspector?.classList.remove('is-open');
        if (inspector) inspector.hidden = true;
        shell?.classList.add('inspector-closed');
      }
      window.AdminI18n?.localise?.(body);
    }

    function renderTenantActionContext(t, actionKey) {
      const body = $('workspaceInspectorBody');
      if (!body) return;
      body.replaceChildren();
      const plan = tenantPlan(t);
      const actionTitles = {
        website: 'Open Studio Website',
        register: 'Open Quick Registration',
        'studio-admin': 'Open Studio Admin',
        cms: 'Open CMS',
        support: 'Enter Support Mode',
        audit: 'View audit history',
        pause: t.status === 'paused' ? 'Reactivate tenant' : 'Pause tenant',
        archive: t.status === 'archived' ? 'Restore tenant' : 'Archive tenant',
        delete: 'Permanent delete tenant',
      };
      const title = actionTitles[actionKey] || 'Tenant action';
      setInspectorHeader('Action context', title);
      const status = document.createElement('div');
      status.className = 'inspector-status';
      const dot = document.createElement('span');
      dot.className = 'inspector-status-dot';
      dot.setAttribute('aria-hidden', 'true');
      const copy = document.createElement('div');
      const name = document.createElement('strong');
      name.textContent = t.name || t.slug;
      const note = document.createElement('div');
      note.className = 'text-muted';
      note.textContent = `${text(t.slug)} · ${planDisplayName(plan.code ? plan : t.plan_code)}`;
      copy.append(name, note);
      status.append(dot, copy);
      body.appendChild(status);

      const context = inspectorSection('What happens next', 'Review before action');
      const contextNote = document.createElement('div');
      contextNote.className = 'action-context-note';
      const notes = {
        website: 'This public surface opens in a new tab and does not require support mode.',
        register: 'This public registration surface opens in a new tab when the tenant is accepting registrations.',
        'studio-admin': 'This tenant-scoped surface opens only after an audited support session starts.',
        cms: 'CMS access is tenant-scoped. Start an audited support session before opening it.',
        support: 'A reason is required and the session is written to the audit log.',
        audit: 'The audit workspace keeps the operator, reason, target and metadata visible.',
        pause: t.status === 'paused' ? 'Reactivation restores the active operational and subscription state.' : 'Pausing keeps tenant content and public records; it changes operational availability.',
        archive: t.status === 'archived' ? 'Restore returns the tenant to a paused state. Archived evidence is retained.' : 'Archiving writes snapshots and removes the tenant from normal operations.',
        delete: 'Permanent deletion is irreversible for live records. Archive evidence remains available for audit.',
      };
      relabel(contextNote, notes[actionKey] || 'Review the requested action before continuing.');
      context.appendChild(contextNote);
      body.appendChild(context);

      const actions = inspectorSection('Action', 'Explicit confirmation');
      const actionList = document.createElement('div');
      actionList.className = 'inspector-action-list';
      if (actionKey === 'website' || actionKey === 'register') {
        inspectorAction(actionList, actionKey === 'website' ? 'Open Studio Website' : 'Open Quick Registration', () => {
          window.open(tenantSurfaceHref(t, actionKey), '_blank', 'noopener');
        });
      } else if (actionKey === 'studio-admin' || actionKey === 'cms') {
        inspectorAction(actionList, 'Enter Support Mode', () => enterSupportMode(t.id, tenantSurfaceHref(t, actionKey === 'cms' ? 'cms' : 'admin')), 'inspector-action inspector-support');
      } else if (actionKey === 'support') {
        inspectorAction(actionList, 'Start Support Mode', () => enterSupportMode(t.id), 'inspector-action inspector-support');
      } else if (actionKey === 'audit') {
        inspectorAction(actionList, 'Open Audit Logs', () => {
          history.pushState(null, '', '#audit');
          setActiveWorkspace('audit');
        });
      } else if (actionKey === 'pause') {
        const next = t.status === 'paused' ? 'reactivate' : 'pause';
        inspectorAction(actionList, next === 'pause' ? 'Pause tenant' : 'Reactivate tenant', () => changeTenantOperationalState(t.id, next), next === 'pause' ? 'inspector-action inspector-support' : 'inspector-action');
      } else if (actionKey === 'archive') {
        if (t.status === 'archived') inspectorAction(actionList, 'Restore tenant', () => restoreTenant(t.id));
        else inspectorAction(actionList, 'Archive tenant', () => archiveTenant(t.id), 'inspector-action inspector-support');
      } else if (actionKey === 'delete') {
        inspectorAction(actionList, 'Permanent delete tenant', () => permanentDeleteTenant(t.id), 'inspector-action inspector-support');
      }
      actions.appendChild(actionList);
      body.appendChild(actions);
      window.AdminI18n?.localise?.(body);
    }

    function openTenantActionContext(id, actionKey, { focus = true } = {}) {
      const t = tenants.find((item) => item.id === id);
      if (!t) return;
      selectedTenantId = id;
      inspectorMode = 'tenant-action';
      inspectorSelection = id;
      inspectorActionKey = actionKey;
      openInspector();
      renderTenantActionContext(t, actionKey);
      document.querySelectorAll('tr[data-tenant-id]').forEach((row) => row.classList.toggle('is-inspector-selected', row.dataset.tenantId === String(id)));
      if (focus && window.matchMedia('(max-width: 1279px)').matches) $('workspaceInspector')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function appendInspectorListSection(parent, title, items, subtitle = 'Review') {
      const section = inspectorSection(title, subtitle);
      const list = document.createElement('ul');
      list.className = 'inspector-list';
      if (!items.length) {
        const empty = document.createElement('li');
        relabel(empty, 'No additional change identified.');
        list.appendChild(empty);
      } else {
        items.forEach((item) => {
          const li = document.createElement('li');
          const label = typeof item === 'string' ? item : item.label;
          relabel(li, label);
          if (typeof item === 'object' && item.value) li.append(' · ', document.createTextNode(item.value));
          list.appendChild(li);
        });
      }
      section.appendChild(list);
      parent.appendChild(section);
      return section;
    }

    function renderEditorInspector() {
      if (!isWorkspaceEditorOpen()) return;
      const body = $('workspaceInspectorBody');
      if (!body) return;
      inspectorMode = `${workspaceEditorKind}-edit`;
      inspectorSelection = workspaceEditorId || null;
      const plan = workspaceEditorKind === 'plan' && workspaceEditorId
        ? plans.find((item) => item.code === workspaceEditorId)
        : null;
      const tenant = workspaceEditorKind === 'tenant' && workspaceEditorId
        ? tenants.find((item) => item.id === workspaceEditorId)
        : null;
      const title = plan?.name || tenant?.name || (workspaceEditorKind === 'plan' ? 'New plan' : 'New tenant');
      setInspectorHeader(workspaceEditorKind === 'plan' ? 'Plan workspace' : 'Tenant workspace', title);
      body.replaceChildren();

      const status = document.createElement('div');
      status.className = 'inspector-status';
      const dot = document.createElement('span');
      dot.className = `inspector-status-dot${workspaceEditorDirty ? ' warning' : ''}`;
      dot.setAttribute('aria-hidden', 'true');
      const copy = document.createElement('div');
      const state = document.createElement('strong');
      relabel(state, workspaceEditorDirty ? 'Unsaved changes' : 'Ready to edit');
      const note = document.createElement('div');
      note.className = 'text-muted';
      relabel(note, 'Save from the center workspace when the review is complete.');
      copy.append(state, note);
      status.append(dot, copy);
      body.appendChild(status);

      const review = inspectorSection('Review before saving', 'Decision guide');
      inspectorMeta(review, 'Workspace', WORKSPACE_LABELS[activeWorkspace]);
      inspectorMeta(review, 'Form state', workspaceEditorDirty ? 'Unsaved changes' : 'Ready');
      if (plan) {
        const affected = tenants.filter((item) => item.plan_code === plan.code).length;
        inspectorMeta(review, 'Tenants on plan', affected);
      }
      if (tenant) {
        inspectorMeta(review, 'Current status', `${tenant.status || '—'} · ${tenant.subscription_status || '—'}`);
      }
      const invalidFields = Array.from(workspaceEditorRoot()?.querySelectorAll('[aria-invalid="true"]') || []);
      inspectorMeta(review, 'Validation errors', invalidFields.length);
      if (invalidFields.length) {
        const alert = document.createElement('div');
        alert.className = 'inspector-alert danger';
        const message = document.createElement('span');
        relabel(message, 'Resolve the highlighted fields before saving.');
        alert.appendChild(message);
        review.appendChild(alert);
      }
      body.appendChild(review);

      if (tenant) {
        const targetPlan = plans.find((item) => item.code === $('m_tenantPlan')?.value) || tenantPlan(tenant);
        const impact = tenantPlanChangeDetails(tenant, targetPlan);
        if (impact) {
          appendInspectorListSection(body, 'Will change', impact.changed.map((item) => ({ label: item.label, value: `${item.from} → ${item.to}` })).concat(
            impact.enabledFeatures.map((key) => ({ label: 'Feature enabled', value: planFeatureLabel(key) })),
            impact.disabledFeatures.map((key) => ({ label: 'Feature disabled', value: planFeatureLabel(key) })),
          ), 'Plan impact');
          appendInspectorListSection(body, 'Will be preserved', [
            'Website, brand and showcase content',
            'Students, courses, registrations and media',
            'Audit history and tenant settings',
          ], 'Content safety');
          const notifications = ['Plan, price and effective date', 'New resource and showcase limits'];
          if (impact.disabledFeatures.length) notifications.push({ label: 'Feature availability', value: impact.disabledFeatures.map(planFeatureLabel).join(', ') });
          if (impact.usageOver.length) notifications.push({ label: 'Current usage is above the new limit', value: impact.usageOver.map((item) => `${item.label} ${item.current} / ${item.limit}`).join(', ') });
          appendInspectorListSection(body, 'Notify tenant', notifications, 'Communication checklist');
        } else {
          appendInspectorListSection(body, 'Plan impact', ['No commercial plan change selected.'], 'Current selection');
        }
      }

      const adjustments = inspectorSection('Needs adjustment', 'Before save');
      const adjustmentList = document.createElement('div');
      adjustmentList.className = 'inspector-action-list';
      if (invalidFields.length) {
        invalidFields.forEach((field) => inspectorAction(adjustmentList, `Fix ${field.getAttribute('aria-label') || field.id}`, () => field.scrollIntoView({ behavior: 'smooth', block: 'center' })));
      }
      const changedTenantPlan = tenant && $('m_tenantPlan') && tenant.plan_code !== $('m_tenantPlan').value;
      if (changedTenantPlan && !$('m_planChangeConfirm')?.checked) {
        inspectorAction(adjustmentList, 'Review and acknowledge plan change', () => $('m_planChangeImpact')?.scrollIntoView({ behavior: 'smooth', block: 'center' }));
      }
      if (!invalidFields.length && !changedTenantPlan) {
        const note = document.createElement('div');
        note.className = 'action-context-note';
        relabel(note, 'No blocking adjustment identified.');
        adjustmentList.appendChild(note);
      }
      adjustments.appendChild(adjustmentList);
      body.appendChild(adjustments);

      const actions = inspectorSection('Workspace actions', 'Safe next steps');
      const actionList = document.createElement('div');
      actionList.className = 'inspector-action-list';
      inspectorAction(actionList, 'Cancel editing', () => closeWorkspaceEditor());
      actions.appendChild(actionList);
      body.appendChild(actions);
      window.AdminI18n?.localise?.(body);
    }

    function attentionIssues(t) {
      const plan = tenantPlan(t);
      const usage = [];
      [['Students', t.student_count, plan.student_limit], ['Storage', t.storage_used_mb, plan.storage_limit_mb], ['Team users', t.user_count, plan.user_limit], ['Showcase works', t.showcase_active_count, plan.showcase_limit]]
        .forEach(([label, current, limit]) => {
          const pct = percent(current, limit);
          if (limit && pct >= 75) usage.push({ label, pct, value: quotaParts(current, limit, label === 'Storage' ? formatStorageMb : (v) => text(v)).label });
        });
      const issues = [];
      if (t.subscription_status === 'past_due') issues.push({ priority: 0, label: 'Subscription past due', reason: 'Subscription record needs review.' });
      if (usage.length) {
        const highest = usage.sort((a, b) => b.pct - a.pct)[0];
        issues.push({ priority: highest.pct >= 90 ? 1 : 2, label: 'Usage approaching limit', reason: `${highest.label} ${highest.pct}% · ${highest.value}` });
      }
      if (t.ends_at && new Date(t.ends_at).getTime() < Date.now()) issues.push({ priority: 1, label: 'Subscription date passed', reason: `Ended ${formatTimestamp(t.ends_at)}.` });
      if (t.subscription_status === 'trialing' && t.trial_ends_at) {
        const days = relativeDays(t.trial_ends_at);
        if (days !== null && days >= 0 && days <= 7) issues.push({ priority: 2, label: 'Trial ending soon', reason: `${days} day${days === 1 ? '' : 's'} left.` });
      }
      if (t.status === 'onboarding' || !t.studio_admin_email) issues.push({ priority: 3, label: 'Onboarding follow-up', reason: t.studio_admin_email ? 'Workspace is still onboarding.' : 'Studio Admin login is not configured.' });
      return issues.sort((a, b) => a.priority - b.priority);
    }

    function attentionItems() {
      return tenants
        .filter((t) => !['archived', 'deleted'].includes(t.status))
        .flatMap((t) => {
          const issue = attentionIssues(t)[0];
          return issue ? [{ ...issue, tenant: t }] : [];
        })
        .sort((a, b) => a.priority - b.priority || String(a.tenant.name || '').localeCompare(String(b.tenant.name || '')));
    }

    function renderAttentionQueue() {
      const queue = $('attentionQueue');
      if (!queue) return;
      const items = attentionItems();
      queue.replaceChildren();
      const badge = $('attentionCountBadge');
      if (badge) badge.textContent = String(items.length);
      if (!items.length) {
        const empty = document.createElement('div');
        empty.className = 'attention-queue-empty';
        relabel(empty, 'No attention items from current tenant and subscription data.');
        queue.appendChild(empty);
        return;
      }
      items.forEach(({ tenant, label, reason }) => {
        const row = document.createElement('div');
        row.className = 'attention-row';
        const copy = document.createElement('div');
        copy.className = 'attention-copy';
        const title = document.createElement('strong');
        relabel(title, label);
        const tenantName = document.createElement('span');
        tenantName.textContent = `${text(tenant.name)} · ${text(tenant.slug)}`;
        copy.append(title, tenantName);
        const detail = document.createElement('div');
        detail.className = 'attention-reason';
        detail.textContent = reason;
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'btn-secondary btn-sm';
        relabel(button, 'Review');
        button.addEventListener('click', () => openTenantInspector(tenant.id));
        row.append(copy, detail, button);
        queue.appendChild(row);
      });
      window.AdminI18n?.localise?.(queue);
    }

    function renderTenantInspector(t) {
      const body = $('workspaceInspectorBody');
      const plan = tenantPlan(t);
      body.replaceChildren();
      setInspectorHeader('Tenant Inspector / 租户详情', t.name || t.slug);

      const status = document.createElement('div');
      status.className = 'inspector-status';
      const statusDot = document.createElement('span');
      const statusValue = t.subscription_status === 'past_due' || t.status === 'paused' ? 'danger' : ['active', 'trialing'].includes(t.subscription_status) ? 'success' : 'warning';
      statusDot.className = `inspector-status-dot ${statusValue === 'danger' ? 'danger' : statusValue === 'warning' ? 'warning' : ''}`;
      statusDot.setAttribute('aria-hidden', 'true');
      const statusCopy = document.createElement('div');
      const statusTitle = document.createElement('strong');
      relabel(statusTitle, `${t.status || '—'} · ${t.subscription_status || '—'}`);
      const statusSub = document.createElement('div');
      statusSub.className = 'text-muted';
      statusSub.textContent = `${text(t.slug)} · ${text(t.owner_email || 'No owner email')}`;
      statusCopy.append(statusTitle, statusSub);
      status.append(statusDot, statusCopy);
      body.appendChild(status);

      const issues = attentionIssues(t);
      if (issues.length) {
        const alert = document.createElement('div');
        alert.className = issues[0].priority === 0 ? 'inspector-alert danger' : 'inspector-alert';
        const alertTitle = document.createElement('strong');
        relabel(alertTitle, issues[0].label);
        const alertCopy = document.createElement('span');
        alertCopy.textContent = issues[0].reason;
        alert.append(alertTitle, alertCopy);
        body.appendChild(alert);
      }

      const subscription = inspectorSection('Subscription', 'Current record');
      inspectorMeta(subscription, 'Plan', planDisplayName(plan.code ? plan : t.plan_code));
      inspectorMeta(subscription, 'Monthly price', plan.monthly_price_aud === undefined ? '—' : money(plan.monthly_price_aud));
      inspectorMeta(subscription, 'Subscription status', t.subscription_status);
      inspectorMeta(subscription, 'Period ends', dateOnly(t.current_period_ends_at || t.ends_at));
      body.appendChild(subscription);

      const usage = inspectorSection('Resource usage', 'Current limits');
      [['Students', t.student_count, plan.student_limit], ['Storage', t.storage_used_mb, plan.storage_limit_mb, formatStorageMb], ['Team users', t.user_count, plan.user_limit], ['Showcase works', t.showcase_active_count, plan.showcase_limit]]
        .forEach(([label, current, limit, format]) => {
          const item = document.createElement('div');
          item.className = 'inspector-usage-row';
          const labelEl = document.createElement('div');
          labelEl.className = 'text-muted';
          relabel(labelEl, label);
          item.appendChild(labelEl);
          addProgressRow(item, current, limit, format);
          usage.appendChild(item);
        });
      body.appendChild(usage);

      const actions = inspectorSection('Quick view', 'Read-only context');
      const actionList = document.createElement('div');
      actionList.className = 'inspector-action-list';
      inspectorAction(actionList, 'View full tenant details', () => openTenantDetailModal(t.id));
      actions.appendChild(actionList);
      body.appendChild(actions);

      const surfaces = inspectorSection('Tenant surfaces', 'Public and audited entry points');
      renderTenantSurfaces(surfaces, t);
      body.appendChild(surfaces);

      const operations = inspectorSection('Operations', 'Use the center Actions column');
      const operationNote = document.createElement('div');
      relabel(operationNote, 'Editing, lifecycle, support and archive actions stay in the center list so the right panel remains a quick read.');
      operations.appendChild(operationNote);
      body.appendChild(operations);
      window.AdminI18n?.localise?.(body);
    }

    function openTenantInspector(id, { focus = true } = {}) {
      const t = tenants.find((item) => item.id === id);
      if (!t) return;
      selectedTenantId = id;
      inspectorMode = 'tenant';
      inspectorSelection = id;
      inspectorActionKey = '';
      openInspector();
      renderTenantInspector(t);
      document.querySelectorAll('tr[data-tenant-id]').forEach((row) => row.classList.toggle('is-inspector-selected', row.dataset.tenantId === String(id)));
        if (focus && window.matchMedia('(max-width: 1279px)').matches) $('workspaceInspector')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function openPlanInspector(plan, { focus = true } = {}) {
      if (!plan) return;
      selectedTenantId = '';
      inspectorMode = 'plan';
      inspectorSelection = plan.code;
      inspectorActionKey = '';
      openInspector();
      document.querySelectorAll('tr[data-plan-code]').forEach((row) => row.classList.toggle('is-inspector-selected', row.dataset.planCode === String(plan.code)));
      setInspectorHeader('Plan Inspector / 套餐详情', planDisplayName(plan));
      const body = $('workspaceInspectorBody');
      body.replaceChildren();
      const state = document.createElement('div');
      state.className = 'inspector-status';
      relabel(state, `${plan.is_public ? 'Published' : 'Not published'} · ${plan.is_recommended ? 'Recommended' : 'Standard plan'}`);
      body.appendChild(state);
      const commercial = inspectorSection('Commercial record', 'Current configuration');
      inspectorMeta(commercial, 'Price / month', money(plan.monthly_price_aud));
      inspectorMeta(commercial, 'Public', plan.is_public ? 'Published' : 'Not published');
      inspectorMeta(commercial, 'Recommended', plan.is_recommended ? 'Yes' : 'No');
      body.appendChild(commercial);
      const limits = inspectorSection('Resource limits', 'Tenant allocation');
      inspectorMeta(limits, 'Students', plan.student_limit);
      inspectorMeta(limits, 'Storage', formatStorageMb(plan.storage_limit_mb));
      inspectorMeta(limits, 'Team users', plan.user_limit);
      inspectorMeta(limits, 'Projects', plan.project_limit);
      inspectorMeta(limits, 'Tenants on plan', tenants.filter((item) => item.plan_code === plan.code).length);
      body.appendChild(limits);
      const operations = inspectorSection('Operations', 'Use the center Actions column');
      const operationNote = document.createElement('div');
      relabel(operationNote, 'Editing and deletion stay in the center list so the right panel remains a quick read.');
      operations.appendChild(operationNote);
      body.appendChild(operations);
      window.AdminI18n?.localise?.(body);
      if (focus && window.matchMedia('(max-width: 1279px)').matches) $('workspaceInspector')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function openAuditInspector(a, { focus = true } = {}) {
      if (!a) return;
      selectedTenantId = '';
      inspectorMode = 'audit';
      inspectorSelection = String(a.id || `${a.created_at}:${a.resource_id}`);
      inspectorActionKey = '';
      openInspector();
      setInspectorHeader('Audit Event Inspector / 审计事件', a.action || 'Audit event');
      document.querySelectorAll('tr[data-audit-id]').forEach((row) => row.classList.toggle('is-inspector-selected', row.dataset.auditId === String(inspectorSelection)));
      const body = $('workspaceInspectorBody');
      body.replaceChildren();
      const event = inspectorSection('Event record', 'Captured activity');
      event.appendChild(buildAuditDetail(a));
      body.appendChild(event);
      window.AdminI18n?.localise?.(body);
      if (focus && window.matchMedia('(max-width: 1279px)').matches) $('workspaceInspector')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function rerenderInspector() {
      if (inspectorMode === 'tenant-action' && selectedTenantId && inspectorActionKey) {
        const t = tenants.find((item) => item.id === selectedTenantId);
        if (t) return openTenantActionContext(selectedTenantId, inspectorActionKey, { focus: false });
      }
      if (inspectorMode === 'tenant' && selectedTenantId) {
        const t = tenants.find((item) => item.id === selectedTenantId);
        if (t) return openTenantInspector(selectedTenantId, { focus: false });
      }
      if (inspectorMode === 'plan-action' && inspectorSelection && inspectorActionKey) {
        const plan = plans.find((item) => item.code === inspectorSelection);
        if (plan) return openPlanActionContext(inspectorSelection, inspectorActionKey, { focus: false });
      }
      if (inspectorMode === 'plan' && inspectorSelection) {
        const plan = plans.find((item) => item.code === inspectorSelection);
        if (plan) return openPlanInspector(plan, { focus: false });
      }
      if (inspectorMode === 'audit' && inspectorSelection) {
        const event = auditLogs.find((item) => String(item.id || `${item.created_at}:${item.resource_id}`) === String(inspectorSelection));
        if (event) return openAuditInspector(event, { focus: false });
      }
      renderWorkspaceInspector();
    }

    function setActiveWorkspace(workspace, { scroll = true } = {}) {
      if (isWorkspaceEditorOpen() && !closeWorkspaceEditor()) return false;
      activeWorkspace = WORKSPACE_IDS.has(workspace) ? workspace : 'overview';
      document.querySelectorAll('[data-workspace]').forEach((section) => {
        const active = section.dataset.workspace === activeWorkspace;
        section.hidden = !active;
        section.setAttribute('aria-hidden', String(!active));
      });
      setActiveNav(`#${activeWorkspace}`);
      renderWorkspaceContext();
      selectedTenantId = '';
      inspectorMode = 'workspace';
      inspectorSelection = null;
      inspectorActionKey = '';
      renderWorkspaceInspector();
      if (scroll && currentUser) {
        requestAnimationFrame(() => {
          const main = document.querySelector('.platform-main');
          if (main) main.scrollTo({ top: 0, behavior: 'smooth' });
        });
      }
    }

    /* Overview counters that name a set of tenants, and the predicate that
       reproduces that set on the client.

       These MUST mirror /v1/admin/usage, and the trap is that most of them are
       defined by the SUBSCRIPTION status while the Status select in the toolbar
       filters the TENANT status — two different fields that happen to share
       several of the same words. Reusing that select would have shown a number
       of rows that quietly disagreed with the number on the card, which is
       worse than a counter that does nothing. */
    const METRIC_FILTERS = {
      all:          { label: 'Total Tenants',
                      match: (t) => !['archived', 'deleted'].includes(t.status) },
      paid:         { label: 'Paid Tenants',
                      match: (t) => t.subscription_status === 'active' && !['archived', 'deleted'].includes(t.status) },
      trial:        { label: 'Trial Tenants',
                      match: (t) => t.subscription_status === 'trialing' && !['archived', 'deleted'].includes(t.status) },
      past_due:     { label: 'Past Due',
                      match: (t) => t.subscription_status === 'past_due' && !['archived', 'deleted'].includes(t.status) },
      onboarding:   { label: 'Onboarding',
                      match: (t) => t.status === 'onboarding' },
      new_30d:      { label: 'New in 30 Days',
                      match: (t) => t.created_at && new Date(t.created_at).getTime() >= Date.now() - 30 * 86400000 },
      trial_ending: { label: 'Trials Ending in 7 Days',
                      match: (t) => {
                        if (t.subscription_status !== 'trialing') return false;
                        if (['archived', 'deleted'].includes(t.status)) return false;
                        const ends = t.trial_ends_at ? new Date(t.trial_ends_at).getTime() : 0;
                        return ends >= Date.now() && ends <= Date.now() + 7 * 86400000;
                      } },
    };

    // Utility functions
    const text = (value) => value === null || value === undefined || value === '' ? '-' : value;
    const esc = window.StudioSaaS.esc;
    /* `label` names the column the cell belongs to. On a phone the tenant
       table becomes one card per row (a 7-column, 1040px table is unreadable
       at 375px), and each cell needs to say which column it is. The label is a
       real text node rather than a ::before/attr() pair so the i18n
       dictionary — which walks text nodes — can translate it. */
    function addCell(row, textValue = '', label = '') {
      const cell = document.createElement('td');
      if (label) {
        const tag = document.createElement('span');
        tag.className = 'cell-label';
        tag.textContent = label;
        cell.appendChild(tag);
      }
      if (textValue !== '') cell.appendChild(document.createTextNode(String(textValue)));
      row.appendChild(cell);
      return cell;
    }
    function addStrongMuted(cell, strongValue, mutedValue = '') {
      const strong = document.createElement('strong');
      strong.textContent = text(strongValue);
      cell.appendChild(strong);
      if (mutedValue !== '') {
        cell.appendChild(document.createElement('br'));
        const muted = document.createElement('span');
        muted.className = 'text-muted';
        muted.textContent = text(mutedValue);
        cell.appendChild(muted);
      }
      return cell;
    }
    function addActionButton(container, label, className, handler) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = className;
      button.textContent = label;
      button.addEventListener('click', (event) => handler(event.currentTarget));
      container.appendChild(button);
      return button;
    }
    function wireQuickViewRow(row, handler, label) {
      row.dataset.quickViewRow = 'true';
      row.tabIndex = 0;
      row.setAttribute('aria-label', label);
      row.addEventListener('click', (event) => {
        if (event.target.closest('button, a, input, select, textarea')) return;
        handler();
      });
      row.addEventListener('keydown', (event) => {
        if (event.key !== 'Enter' && event.key !== ' ') return;
        event.preventDefault();
        handler();
      });
    }
    function appendEmptyRow(tbody, colspan, message) {
      const row = document.createElement('tr');
      const cell = addCell(row);
      const empty = document.createElement('div');
      cell.colSpan = colspan;
      empty.className = 'empty-state';
      empty.textContent = message;
      // Empty states are written from script on every re-render, so the
      // dictionary pass that ran at load has long since gone by.
      window.AdminI18n?.localise?.(empty);
      cell.appendChild(empty);
      tbody.appendChild(row);
    }
	    /* Calendar date from whatever the API sent, as `YYYY-MM-DD`.
	     *
	     * This used to be `String(value).slice(0, 10)`, which assumes ISO. The
	     * API does not send ISO: `jsonify` renders a datetime as RFC 1123, so
	     * `Wed, 29 Jul 2026 00:00:00 GMT` was sliced to `Wed, 29 Ju`. That is
	     * not a valid `<input type="date">` value, so every subscription date
	     * field rendered EMPTY — and the save path reads
	     * `$('m_startsAt').value || null`, so opening a tenant, changing a
	     * phone number and pressing save wrote NULL over all four dates. The
	     * displayed `Wed, 29 Ju` in the detail modal was the same bug wearing
	     * its other face.
	     *
	     * Read in UTC, deliberately. These are calendar dates, and the server
	     * sends GMT midnight; taking local components would move the day
	     * backwards for every operator west of Greenwich and silently shift
	     * a subscription by one day each time the form was saved.
	     */
	    const dateOnly = (value) => {
	      if (!value) return '';
	      const raw = String(value);
	      // Already ISO (or ISO-prefixed): trust it rather than round-tripping
	      // through Date, which is what introduces timezone questions.
	      if (/^\d{4}-\d{2}-\d{2}/.test(raw)) return raw.slice(0, 10);
	      const parsed = new Date(raw);
	      if (Number.isNaN(parsed.getTime())) return '';
	      const pad = (n) => String(n).padStart(2, '0');
	      return `${parsed.getUTCFullYear()}-${pad(parsed.getUTCMonth() + 1)}-${pad(parsed.getUTCDate())}`;
	    };
	    const money = (value) => `AUD ${Number(value || 0)}`;
	    // Locale-aware timestamp in the viewer's local timezone (audit logs
	    // arrive as raw RFC 1123 GMT strings). zh: 2026-07-26 21:21; en:
	    // 26 Jul 2026 21:21. Falls back to the raw value if unparseable.
	    const MONTHS_EN = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
	    const adminLanguage = () => (window.AdminI18n && window.AdminI18n.language)
	      || (localStorage.getItem('studiosaas_admin_language') === 'en' ? 'en' : 'zh');
	    function formatTimestamp(value) {
	      if (!value) return '-';
	      const date = new Date(value);
	      if (Number.isNaN(date.getTime())) return String(value);
	      const pad = (n) => String(n).padStart(2, '0');
	      const time = `${pad(date.getHours())}:${pad(date.getMinutes())}`;
	      if (adminLanguage() === 'en') return `${date.getDate()} ${MONTHS_EN[date.getMonth()]} ${date.getFullYear()} ${time}`;
	      return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${time}`;
	    }
	    const percent = (value, limit) => limit ? Math.min(100, Math.round((Number(value || 0) / Number(limit || 1)) * 100)) : 0;
	    let INDUSTRY_PRESETS = {
	      general: { label: 'General', labelZh: '通用', slogan: 'A learning path that fits every student.' }
	    };
	    async function loadIndustryPresets() {
	      try {
	        const response = await fetch('/v1/industry-presets', { credentials: 'same-origin' });
	        if (!response.ok) throw new Error(`Preset request failed (${response.status})`);
	        const data = await response.json();
	        if (data.presets && Object.keys(data.presets).length) INDUSTRY_PRESETS = data.presets;
	      } catch (error) {
	        console.warn('Using the generic industry preset.', error);
	      }
	    }
	    const categoryOptions = (selected = 'general') => Object.entries(INDUSTRY_PRESETS)
	      .map(([key, preset]) => `<option value="${esc(key)}" ${key === selected ? 'selected' : ''}>${esc(preset.label)}</option>`)
	      .join('');
	    const presetSlogan = (category) => (INDUSTRY_PRESETS[category] || INDUSTRY_PRESETS.general).slogan;

    // Toast notifications
    function showToast(message, type = 'success') {
      const container = $('toastContainer');
      const toast = document.createElement('div');
      toast.className = `toast ${type}`;
      const icon = type === 'success' ? '✓' : type === 'error' ? '✕' : '!';
      const iconEl = document.createElement('span');
      iconEl.style.fontSize = '18px';
      iconEl.setAttribute('aria-hidden', 'true');
      iconEl.textContent = icon;
      const messageEl = document.createElement('span');
      messageEl.textContent = message;
      toast.append(iconEl, messageEl);
      container.appendChild(toast);
      setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => toast.remove(), 300);
      }, 4000);
    }

    // Loading state
    function setLoading(loading) {
      isLoading = loading;
      $('refreshBtn').classList.toggle('btn-loading', loading);
      $('refreshIcon').textContent = loading ? '' : '↻';
      if (loading) {
        const spinner = document.createElement('span');
        spinner.className = 'loading';
        $('refreshIcon').appendChild(spinner);
      } else {
        const spinner = $('refreshIcon').querySelector('.loading');
        if (spinner) spinner.remove();
      }
      renderWorkspaceContext();
    }

    // API call with error handling
    async function api(path, options = {}) {
      const base = '/v1';
      try {
        const res = await fetch(base + path, {
          ...options,
          credentials: 'include',
          headers: { 'Content-Type': 'application/json', ...(options.headers || {}) }
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          const err = new Error(data.message || data.error || `${res.status} ${path}`);
          err.status = res.status;
          err.payload = data;
          throw err;
        }
        return data;
      } catch (err) {
        if (err.status !== 401) showToast(err.message, 'error');
        throw err;
      }
    }

    function setAuthState(user) {
      currentUser = user || null;
      const signedIn = Boolean(currentUser);
      $('loginPanel').classList.toggle('hidden', signedIn);
      $('adminContent').classList.toggle('hidden', !signedIn);
      $('logoutBtn').classList.toggle('hidden', !signedIn);
      $('changePasswordBtn').classList.toggle('hidden', !signedIn);
      $('refreshBtn').disabled = !signedIn;
      $('superNav').classList.toggle('hidden', !signedIn);
      document.querySelectorAll('.requires-auth').forEach((element) => element.classList.toggle('hidden', !signedIn));
      $('authStatus').textContent = signedIn ? `Signed in: ${currentUser.email || currentUser.full_name || currentUser.id}` : 'Not signed in';
      updateWorkspaceHeaderOffset();
      if (signedIn) {
        if ($('workspaceInspector')?.hidden) openInspector();
        setActiveWorkspace(workspaceFromHash(), { scroll: true });
      }
      else renderWorkspaceContext();
    }

    function hasSuperAdminRole(data) {
      // Only the platform membership (tenant_slug NULL) counts — a legacy
      // tenant-scoped super_admin row is not a platform administrator
      // (mirrors _has_platform_super_admin_membership on the backend).
      return (data.memberships || []).some(
        (membership) => membership.role === 'super_admin' && !membership.tenant_slug);
    }

    async function checkSession() {
      try {
        const data = await api('/auth/me');
        if (!hasSuperAdminRole(data)) {
          await api('/auth/logout', { method: 'POST' }).catch(() => {});
          setAuthState(null);
          showToast('Please log in with a Super Admin account.', 'error');
          return;
        }
        setAuthState(data.user);
        await refresh();
      } catch (err) {
        setAuthState(null);
        if (err.status && err.status !== 401) showToast(`Session check failed: ${err.message}`, 'error');
      }
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

    async function loginSuperAdmin(event) {
      event.preventDefault();
      clearLoginError();
      const email = $('loginEmail').value.trim();
      const password = $('loginPassword').value;
      if (!email || !password) {
        showToast('Email and password are required.', 'error');
        setLoginError('Email and password are required.', !email ? $('loginEmail') : $('loginPassword'));
        return;
      }
      const btn = $('loginBtn');
      btn.disabled = true;
      const originalLabel = btn.textContent;
      btn.textContent = 'Logging in…';
      try {
        await api('/auth/login', {
          method: 'POST',
          body: JSON.stringify({ email, password, rememberMe: $('loginRemember').checked })
        });
        $('loginPassword').value = '';
        showToast('Logged in.');
        await checkSession();
      } catch (err) {
        if (err.status === 429) {
          showToast('Too many login attempts — please wait a minute and try again.', 'error');
          setLoginError('Too many login attempts — please wait a minute and try again.');
        } else {
          showToast(err.status === 401 ? 'Invalid email or password.' : err.message, 'error');
          setLoginError(err.status === 401 ? 'Invalid email or password.' : err.message,
            err.status === 401 ? $('loginPassword') : null);
        }
      } finally {
        btn.disabled = false;
        btn.textContent = originalLabel;
      }
    }

    function wirePasswordToggle(inputId, toggleId) {
      const input = $(inputId);
      const toggle = $(toggleId);
      if (!input || !toggle) return;
      toggle.addEventListener('click', () => {
        const showing = input.type === 'text';
        input.type = showing ? 'password' : 'text';
        toggle.textContent = showing ? 'Show' : 'Hide';
      });
    }
    wirePasswordToggle('loginPassword', 'loginPwToggle');

    async function logoutSuperAdmin() {
      await api('/auth/logout', { method: 'POST' }).catch(() => {});
      setAuthState(null);
      tenants = [];
      plans = [];
      auditLogs = [];
      workspaceFailures = [];
      workspaceLoadError = false;
      lastRefreshAt = null;
      // Reset every stat card that actually exists on this page (ids match the
      // .stats-grid markup); the null guard keeps logout from throwing if a
      // card is ever renamed again.
      ['tenantCount', 'mrrCount', 'paidTenantCount', 'trialTenantCount',
       'onboardingTenantCount', 'pastDueTenantCount', 'trialEndingCount', 'newTenantCount']
        .forEach((id) => { const el = $(id); if (el) el.textContent = '-'; });
      $('acquisitionFunnel').textContent = 'Loading registration conversion…';
      $('acquisitionFunnel').classList.add('empty-state');
      $('tenantsBody').innerHTML = '';
      $('plansBody').innerHTML = '';
      $('auditBody').innerHTML = '';
      $('auditCountLabel').textContent = '';
      $('auditSearch').value = '';
      closeWorkspaceEditor({ confirm: false, focus: false });
      closeInspector();
      $('attentionQueue').replaceChildren();
      $('attentionCountBadge').textContent = '0';
      auditPage = 0;
      setMetricFilter('');
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
      try {
        await api('/auth/change-password', {
          method: 'POST',
          body: JSON.stringify({ oldPassword, newPassword })
        });
        closeModal();
        showToast('Password updated.');
      } catch (err) {
        showToast(err.status === 401 ? 'Current password is incorrect.' : err.message, 'error');
      }
    }

    // Modal functions
    let modalReturnFocus = null;

    function openModal(title, bodyHtml, footerHtml) {
      modalReturnFocus = document.activeElement;
      $('modalOverlay').classList.remove('detail-overlay');
      $('modalOverlay').querySelector('.modal').classList.remove('detail-modal');
      $('modalTitle').textContent = title;
      $('modalBody').innerHTML = bodyHtml;
      $('modalFooter').innerHTML = footerHtml;
      $('modalOverlay').classList.add('active');
      const focusTarget = $('modalBody').querySelector('input, select, textarea, button') || $('modalFooter').querySelector('button');
      if (focusTarget) focusTarget.focus();
    }

    function closeModal() {
      $('modalOverlay').classList.remove('active');
      $('modalOverlay').classList.remove('detail-overlay');
      $('modalOverlay').querySelector('.modal').classList.remove('detail-modal');
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

    // Status pill with icon. SVG-only (v7.3.2 icon rule): the old text glyphs
    // ⚠ and ⏸ render as emoji on some platforms. Decorative — the status word
    // next to each icon carries the meaning.
    const pillIcon = (body) => `<svg class="pill-icon" viewBox="0 0 12 12" aria-hidden="true" focusable="false">${body}</svg>`;
    const PILL_CROSS = pillIcon('<path d="M2.5 2.5l7 7M9.5 2.5l-7 7" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>');
    const STATUS_PILL_ICONS = {
      lead: pillIcon('<circle cx="6" cy="6" r="4.25" fill="none" stroke="currentColor" stroke-width="1.5"/>'),
      onboarding: pillIcon('<circle cx="6" cy="6" r="4.25" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M1.75 6a4.25 4.25 0 008.5 0z" fill="currentColor"/>'),
      active: pillIcon('<circle cx="6" cy="6" r="4.75" fill="currentColor"/>'),
      trialing: pillIcon('<circle cx="6" cy="6" r="4.25" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M6 1.75a4.25 4.25 0 000 8.5z" fill="currentColor"/>'),
      trial: pillIcon('<path d="M6 1.2L10.8 6 6 10.8 1.2 6z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>'),
      past_due: pillIcon('<path d="M6 1.4L11 10.4H1z" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/><path d="M6 4.4v2.6" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/><circle cx="6" cy="8.9" r="0.7" fill="currentColor"/>'),
      cancelled: PILL_CROSS,
      paused: pillIcon('<path d="M4 2.5v7M8 2.5v7" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>'),
      archived: pillIcon('<rect x="2" y="2" width="8" height="8" rx="1" fill="none" stroke="currentColor" stroke-width="1.5"/>'),
      deleted: PILL_CROSS
    };

    function appendPill(cell, value) {
      const cls = value === 'active' || value === 'trialing' || value === 'trial' ? 'pill active' :
                  value === 'past_due' ? 'pill past_due' : 'pill';
      const span = document.createElement('span');
      span.className = cls;
      span.innerHTML = STATUS_PILL_ICONS[value] || '';
      span.appendChild(document.createTextNode(text(value)));
      cell.appendChild(span);
      return span;
    }

    // Generic icon pill (same component as status pills): static SVG via
    // innerHTML, label via a text node so admin-i18n can translate it.
    function appendPillWithIcon(parent, label, className, icon) {
      const span = document.createElement('span');
      span.className = className;
      span.innerHTML = icon || '';
      span.appendChild(document.createTextNode(label));
      parent.appendChild(span);
      return span;
    }

    // Health badges reuse the pill component with an icon and the audited
    // WCAG-AA pill colour pairs (green = healthy, amber = needs action,
    // warm neutral = inert and test fixture). Colour never carries meaning
    // alone — the label text stays next to every icon.
    const PILL_CHECK = pillIcon('<path d="M2.6 6.4l2.3 2.3 4.5-5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>');
    const PILL_ALERT = STATUS_PILL_ICONS.past_due;
    const PILL_FLASK = pillIcon('<path d="M4.7 1.6h2.6M5.3 1.6v3.1L2.5 9.2a1.3 1.3 0 001.1 2h4.8a1.3 1.3 0 001.1-2L6.7 4.7V1.6" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round" stroke-linecap="round"/>');
    const HEALTH_PILLS = {
      'Healthy': ['pill active', PILL_CHECK],
      'Needs setup': ['pill warning', PILL_ALERT],
      'Subscription past due': ['pill past_due', PILL_ALERT],
      'No admin login': ['pill warning', PILL_ALERT],
      'Paused': ['pill paused', STATUS_PILL_ICONS.paused],
      'Archived': ['pill archived', STATUS_PILL_ICONS.archived],
      'Test fixture': ['pill fixture', PILL_FLASK]
    };

    function appendHealthPill(parent, t) {
      const label = healthLabel(t);
      const [className, icon] = HEALTH_PILLS[label] || ['pill warning', PILL_ALERT];
      return appendPillWithIcon(parent, label, className, icon);
    }

    function tenantPlan(t) {
      return plans.find((item) => item.code === t.plan_code) || {};
    }

    const PLAN_DISPLAY_NAMES = {
      starter: { en: 'Starter', zh: '入门版' },
      studio: { en: 'Studio', zh: '工作室版' },
      growth: { en: 'Growth', zh: '成长版' },
    };

    function planDisplayName(planOrCode) {
      const plan = typeof planOrCode === 'object' && planOrCode
        ? planOrCode
        : plans.find((item) => item.code === planOrCode) || { code: planOrCode };
      const code = String(plan.code || '').toLowerCase();
      const canonical = PLAN_DISPLAY_NAMES[code];
      if (canonical) return window.AdminI18n?.language === 'zh' ? canonical.zh : canonical.en;
      return text(plan.name || code);
    }

    function formatStorageMb(value) {
      const mb = Number(value || 0);
      if (mb >= 1024) return `${(mb / 1024).toFixed(mb >= 10240 ? 0 : 1)} GB`;
      return `${mb} MB`;
    }

    /* A subscription date field.
     *
     * The native picker stays: it brings a calendar, keyboard entry, locale
     * formatting and screen-reader support that a hand-built year/month/day
     * trio would have to reimplement and would get wrong first. What it does
     * not bring is the two things an operator actually wants — a way to say
     * "a year from now" without counting, and a reading of how far away the
     * date is. Those are added around it.
     *
     * It looked broken before this release, but the control was never the
     * problem: the value handed to it was `Wed, 29 Ju`, so the browser
     * discarded it and rendered an empty field.
     */
    function dateField(id, label, value) {
      const iso = dateOnly(value);
      return `
        <div class="form-group date-field" data-date-field="${esc(id)}">
          <label for="${esc(id)}">${esc(label)}</label>
          <input id="${esc(id)}" type="date" value="${esc(iso)}" oninput="refreshDateHint('${esc(id)}')">
          <div class="date-quick">
            <button type="button" class="chip" onclick="setDateField('${esc(id)}', 0)">Today</button>
            <button type="button" class="chip" onclick="setDateField('${esc(id)}', 30)">+1 month</button>
            <button type="button" class="chip" onclick="setDateField('${esc(id)}', 365)">+1 year</button>
            <button type="button" class="chip" onclick="setDateField('${esc(id)}', null)">Clear</button>
          </div>
          <small class="date-hint" id="${esc(id)}_hint"></small>
        </div>`;
    }

    function isoToday(offsetDays = 0) {
      const now = new Date();
      const day = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()));
      day.setUTCDate(day.getUTCDate() + offsetDays);
      return day.toISOString().slice(0, 10);
    }

    function setDateField(id, offsetDays) {
      const input = $(id);
      if (!input) return;
      // Relative to the field's own value where it has one, so "+1 year" on a
      // period end means a year after that end, not a year from today.
      const base = offsetDays === null ? null
        : (input.value && offsetDays !== 0 ? input.value : isoToday());
      if (offsetDays === null) {
        input.value = '';
      } else {
        const day = new Date(`${base}T00:00:00Z`);
        day.setUTCDate(day.getUTCDate() + offsetDays);
        input.value = day.toISOString().slice(0, 10);
      }
      refreshDateHint(id);
      validateSubscriptionDates();
    }

    function refreshDateHint(id) {
      const input = $(id);
      const hint = $(`${id}_hint`);
      if (!input || !hint) return;
      const days = input.value ? relativeDays(input.value) : null;
      hint.replaceChildren();
      hint.className = 'date-hint';
      if (days !== null) {
        // Same rule as the detail view: the start date is not a deadline, so
        // a start in the past is history rather than a problem.
        const badge = dateRelativeBadge(days, id !== 'm_startsAt');
        hint.className = `date-hint ${badge.className.replace('date-rel', '').trim()}`.trim();
        hint.append(...badge.childNodes);
      }
      window.AdminI18n?.localise?.(hint);
      validateSubscriptionDates();
    }

    /* The four dates have to describe a subscription that could exist.

       Mirrors `lifecycle.validate_subscription_dates`, which is the authority
       — this copy exists so the operator learns before they press Save rather
       than from a red toast afterwards. Checking only against the start (as
       the first version did) let "cancellation before the period it cancels"
       through, which is exactly what the owner's screenshot showed.

       Every pair, in order, because the rule is transitive and stating it
       pairwise is what makes each message name the two dates involved. */
    const SUBSCRIPTION_DATE_FIELDS = [
      ['m_startsAt', 'Subscription start'],
      ['m_trialEndsAt', 'Trial end'],
      ['m_currentPeriodEndsAt', 'Current period end'],
      ['m_endsAt', 'Cancellation / expiry'],
    ];

    function validateSubscriptionDates() {
      const box = $('m_dateError');
      if (!box) return true;
      const value = (id) => ($(id) ? $(id).value : '');
      /* Each problem is a list of nodes rather than one sentence. An
         interpolated "Trial end is before subscription start." matches
         nothing in the dictionary; label + "is before" + label composes
         correctly in English and in Chinese («试用结束早于订阅开始»), and
         every piece is a whole entry the dictionary can find. */
      const problems = [];
      const offenders = [];
      SUBSCRIPTION_DATE_FIELDS.forEach(([earlierId, earlierLabel], index) => {
        const earlier = value(earlierId);
        if (!earlier) return;
        SUBSCRIPTION_DATE_FIELDS.slice(index + 1).forEach(([laterId, laterLabel]) => {
          const later = value(laterId);
          if (later && later < earlier) {
            problems.push([laterLabel, 'is before', earlierLabel]);
            offenders.push(laterId);
          }
        });
      });
      // A status that names a date it does not have.
      const status = $('m_subscriptionStatus')?.value || '';
      if (status === 'trialing' && !value('m_trialEndsAt')) {
        problems.push(['A trialing subscription needs a trial end date.']);
        offenders.push('m_trialEndsAt');
      }
      if (status === 'cancelled' && !value('m_endsAt')) {
        problems.push(['A cancelled subscription needs a cancellation date.']);
        offenders.push('m_endsAt');
      }
      box.replaceChildren();
      box.hidden = !problems.length;
      SUBSCRIPTION_DATE_FIELDS.forEach(([id]) => $(id)?.removeAttribute('aria-invalid'));
      offenders.forEach((id) => $(id)?.setAttribute('aria-invalid', 'true'));
      refreshEditorTabFlags();
      if (problems.length) {
        problems[0].forEach((part, index) => {
          if (index) box.appendChild(document.createTextNode(' '));
          const piece = document.createElement('span');
          piece.textContent = part;
          box.appendChild(piece);
        });
        window.AdminI18n?.localise?.(box);
      }
      return !problems.length;
    }

    /* `usageText` built the same reading as a sentence and lived here. The
       usage column renders bars now (`renderUsageCell`) and every quota
       figure on the page goes through `quotaParts`, so there is one place
       that decides how a limit is written. */

    function isTestTenant(t) {
      if (t.is_test === true) return true;
      const slug = String(t.slug || '');
      return slug.startsWith('isolation-') || slug.startsWith('test-') || String(t.owner_email || '').endsWith('@studiosaas.local');
    }

    function accessStatus(t) {
      if (['archived', 'deleted'].includes(t.status)) return 'Disabled';
      if (t.status === 'paused') return 'Limited';
      return 'Enabled';
    }

    function tenantRisks(t) {
      const plan = tenantPlan(t);
      const risks = [];
      if (!t.owner_email) risks.push('No owner assigned');
      if (!t.studio_admin_email) risks.push('No admin login');
      if (!t.billing_email) risks.push('Billing email missing');
      if (!t.portal_published) risks.push('Website not published');
      if (!t.logo_ready || !t.hero_ready || !t.contact_ready) risks.push('Brand setup incomplete');
      if (!t.studio_admin_last_login) risks.push('Owner has not signed in');
      if (t.ends_at && new Date(t.ends_at).getTime() < Date.now()) risks.push('Subscription expired');
      if (plan.storage_limit_mb && percent(t.storage_used_mb, plan.storage_limit_mb) >= 85) risks.push('Storage near limit');
      if (plan.student_limit && percent(t.student_count, plan.student_limit) >= 85) risks.push('Student limit near limit');
      return risks;
    }

    function onboardingChecklist(t) {
      return [
        ['Owner assigned', Boolean(t.owner_email)],
        ['Studio Admin login configured', Boolean(t.studio_admin_email)],
        ['Owner has signed in', Boolean(t.studio_admin_last_login)],
        ['Logo configured', Boolean(t.logo_ready)],
        ['Hero and contact ready', Boolean(t.hero_ready && t.contact_ready)],
        ['Studio Website published', Boolean(t.portal_published)]
      ];
    }

    function onboardingProgress(t) {
      const steps = onboardingChecklist(t);
      return `${steps.filter(([, complete]) => complete).length} / ${steps.length}`;
    }

    function healthLabel(t) {
      if (isTestTenant(t)) return 'Test fixture';
      if (t.status === 'archived') return 'Archived';
      if (t.status === 'paused') return 'Paused';
      if (t.subscription_status === 'past_due') return 'Subscription past due';
      if (!t.studio_admin_email) return 'No admin login';
      if (tenantRisks(t).length) return 'Needs setup';
      return 'Healthy';
    }

    function appendSmallBadge(parent, label, className = 'pill') {
      const badge = document.createElement('span');
      badge.className = className;
      badge.textContent = label;
      parent.appendChild(badge);
      return badge;
    }

    function addDisabledNote(parent, message) {
      const note = document.createElement('div');
      note.className = 'disabled-note';
      note.textContent = message;
      parent.appendChild(note);
    }

    function addActionLink(container, label, href, disabledReason = '') {
      const link = document.createElement('a');
      link.className = `btn-secondary${disabledReason ? ' is-disabled' : ''}`;
      link.href = disabledReason ? '#' : href;
      link.target = disabledReason ? '' : '_blank';
      link.rel = disabledReason ? '' : 'noopener';
      link.textContent = label;
      if (disabledReason) link.title = disabledReason;
      container.appendChild(link);
      return link;
    }

    function tenantSurfaceHref(t, surface) {
      const slug = encodeURIComponent(String(t.slug || ''));
      const routes = {
        portal: `/${slug}`,
        cms: `/${slug}/cms`,
        register: `/${slug}/register`,
        admin: `/${slug}/studio-admin`
      };
      return routes[surface] || routes.portal;
    }

    function renderTenantSurfaces(parent, t) {
      const disabled = ['archived', 'deleted'].includes(t.status);
      const grid = document.createElement('div');
      grid.className = 'surface-link-grid';
      // CMS and Admin are tenant-scoped: without an active support session the
      // backend answers 403 support_session_required, so those two route
      // through the support-mode modal. Portal and Register stay public links.
      [
        ['portal', 'Portal', false],
        ['cms', 'CMS', true],
        ['register', 'Register', false],
        ['admin', 'Admin', true]
      ].forEach(([surface, label, gated]) => {
        const link = document.createElement(gated && !disabled ? 'button' : 'a');
        const mark = document.createElement('span');
        const textNode = document.createElement('span');
        link.id = `surface-${t.id}-${surface}`;
        link.className = `surface-mini ${disabled ? 'disabled' : ''}`;
        mark.className = 'mark';
        mark.setAttribute('aria-hidden', 'true');
        textNode.textContent = label;
        if (gated && !disabled) {
          link.type = 'button';
          link.title = 'Opens via Support Mode (audited).';
          mark.innerHTML = ICON_SHIELD;
          link.addEventListener('click', () => enterSupportMode(t.id, tenantSurfaceHref(t, surface)));
        } else {
          link.href = disabled ? '#' : tenantSurfaceHref(t, surface);
          link.target = disabled ? '' : '_blank';
          link.rel = disabled ? '' : 'noopener';
          link.title = disabled ? 'Archived or deleted tenants cannot be opened.' : `Open ${label}`;
          mark.textContent = disabled ? '-' : '↗';
        }
        link.append(mark, textNode);
        grid.appendChild(link);
      });
      parent.appendChild(grid);
      if (disabled) appendSmallBadge(parent, 'Surfaces disabled', 'pill archived');
      else {
        if (!t.studio_admin_email) appendSmallBadge(parent, 'No admin login', 'pill warning');
        if (t.status === 'paused') appendSmallBadge(parent, 'Register paused', 'pill warning');
        // Surface checks are intentionally on-demand in tenant details. A list
        // refresh must not fetch four full HTML pages per tenant.
      }
    }

    function slugifyTenantName(name) {
      return String(name || '')
        .toLowerCase()
        .replace(/&/g, ' and ')
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '')
        .slice(0, 63) || 'new-studio';
    }

    function addDaysIso(days) {
      const date = new Date();
      date.setDate(date.getDate() + days);
      return date.toISOString().slice(0, 10);
    }

    // Fill plan select dropdowns
    function fillPlanSelect() {
      $('planFilter').replaceChildren();
      const allPlans = document.createElement('option');
      allPlans.value = '';
      allPlans.textContent = 'All Plans';
      $('planFilter').appendChild(allPlans);
      plans.forEach((p) => {
        const option = document.createElement('option');
        option.value = text(p.code);
        option.textContent = planDisplayName(p);
        $('planFilter').appendChild(option);
      });
      const categories = [...new Set(tenants.map((tenant) => tenant.category || 'general'))].sort();
      $('categoryFilter').replaceChildren();
      const allCategories = document.createElement('option');
      allCategories.value = '';
      allCategories.textContent = 'All Categories';
      $('categoryFilter').appendChild(allCategories);
      categories.forEach((category) => {
        const option = document.createElement('option');
        option.value = text(category);
        option.textContent = text((INDUSTRY_PRESETS[category] || { label: category }).label);
        $('categoryFilter').appendChild(option);
      });
    }

    /* ── the editor's tabs ────────────────────────────────────────────────
       Until v9.9.5 this was a strip of buttons that scrolled to an accordion,
       and the strip did not work at all: editTenant() rendered it and never
       called the function that attached the listeners — the only call sat in
       addPlan(), an editor with no such strip. The accordions still worked
       because <details> needs no JavaScript, which is exactly why nobody
       noticed the tabs were inert.

       It is a real tablist now, the same component the tenant detail view
       uses. Splitting a form across tabs hides fields, so two things are
       owed back to the operator and both are implemented here: a tab shows
       how many invalid fields are behind it, and a dot when a field on it has
       been changed. Saving jumps to the first tab that is holding an error
       rather than reporting a failure the operator cannot see. */
    function editorTabButton(key, label, selected = false) {
      return `<button type="button" class="tab" role="tab" id="editorTab-${esc(key)}"`
        + ` data-editor-tab="${esc(key)}" aria-controls="editor-section-${esc(key)}"`
        + ` aria-selected="${selected ? 'true' : 'false'}" tabindex="${selected ? '0' : '-1'}">`
        + `<span class="tab-label">${esc(label)}</span>`
        + `<span class="tab-flag" data-tab-flag hidden></span></button>`;
    }

    /* The line that used to be the <summary>. A tab label has to stay short
       enough to sit in a row, so the context it dropped — which studio, which
       plan, which login — is restated at the top of the panel. */
    function editorPanelLead(title, detailHtml) {
      return `<p class="editor-panel-lead"><span>${esc(title)}</span>`
        + (detailHtml ? ` <span class="text-muted">${/*safe*/detailHtml}</span>` : '')
        + `</p>`;
    }

    function editorTabButtons(root) {
      return Array.from((root || workspaceEditorRoot() || document).querySelectorAll('.editor-tabs [role="tab"]'));
    }

    function editorPanelFor(key, root) {
      const scope = root || workspaceEditorRoot() || document;
      return scope.querySelector(`[data-editor-panel="${CSS.escape(key)}"]`);
    }

    function selectEditorTab(key, { focus = false } = {}) {
      const tabs = editorTabButtons();
      if (!tabs.length) return false;
      const wanted = tabs.find((tab) => tab.dataset.editorTab === key) || tabs[0];
      tabs.forEach((tab) => {
        const on = tab === wanted;
        tab.setAttribute('aria-selected', String(on));
        tab.tabIndex = on ? 0 : -1;
        const panel = editorPanelFor(tab.dataset.editorTab);
        if (panel) panel.hidden = !on;
      });
      if (focus) wanted.focus();
      // A tab far to the right is worth nothing if the strip never scrolls to
      // it — this is how "Subscription & Plan" is reached from the row menu.
      wanted.scrollIntoView({ block: 'nearest', inline: 'nearest' });
      return true;
    }

    /* What each tab is hiding: an invalid-field count, or a change dot. */
    function refreshEditorTabFlags() {
      editorTabButtons().forEach((tab) => {
        const panel = editorPanelFor(tab.dataset.editorTab);
        const flag = tab.querySelector('[data-tab-flag]');
        if (!panel || !flag) return;
        const invalid = panel.querySelectorAll('[aria-invalid="true"]').length;
        const alerts = Array.from(panel.querySelectorAll('[role="alert"]'))
          .filter((node) => !node.hidden && node.textContent.trim()).length;
        const errors = invalid + alerts;
        const edited = Boolean(panel.querySelector('[data-edited="true"]'));
        if (errors) {
          flag.hidden = false;
          flag.dataset.kind = 'error';
          flag.textContent = String(errors);
          // Announced, because the count changes while focus is elsewhere.
          tab.setAttribute('aria-describedby', flag.id || '');
        } else if (edited) {
          flag.hidden = false;
          flag.dataset.kind = 'edited';
          flag.textContent = '';
        } else {
          flag.hidden = true;
          flag.removeAttribute('data-kind');
          flag.textContent = '';
        }
      });
    }

    /* Jump to whichever tab is holding the first problem, then focus it. */
    function revealEditorProblem(fieldId) {
      const field = fieldId ? $(fieldId) : null;
      const panel = field ? field.closest('[data-editor-panel]') : null;
      const key = panel?.dataset.editorPanel;
      if (key) selectEditorTab(key);
      refreshEditorTabFlags();
      if (field) {
        field.scrollIntoView({ block: 'center' });
        if (typeof field.focus === 'function' && !field.disabled) field.focus();
      }
      return Boolean(key);
    }

    function wireEditorTabs(focusSection = 'basic') {
      const root = workspaceEditorRoot();
      const tabs = editorTabButtons(root);
      if (!tabs.length) return;
      const order = tabs.map((tab) => tab.dataset.editorTab);
      tabs.forEach((tab) => {
        tab.addEventListener('click', () => selectEditorTab(tab.dataset.editorTab));
        // Left/right move between tabs, which is what a tablist owes a
        // keyboard user; Tab itself walks into the visible panel.
        tab.addEventListener('keydown', (event) => {
          const at = order.indexOf(tab.dataset.editorTab);
          let next = null;
          if (event.key === 'ArrowRight') next = order[(at + 1) % order.length];
          if (event.key === 'ArrowLeft') next = order[(at - 1 + order.length) % order.length];
          if (event.key === 'Home') next = order[0];
          if (event.key === 'End') next = order[order.length - 1];
          if (!next) return;
          event.preventDefault();
          selectEditorTab(next, { focus: true });
        });
      });
      selectEditorTab(focusSection || 'basic');
      refreshEditorTabFlags();
    }

    // Edit tenant in the center workspace; the Inspector remains the review context.
    function editTenant(id, { focusSection = 'basic', actionContext = '' } = {}) {
      const t = tenants.find((item) => item.id === id);
      if (!t) return;
      if ($('modalOverlay')?.classList.contains('active')) closeModal();
      editingTenantId = id;
      workspaceEditorFocusSection = focusSection;
      const formHtml = `
        <div class="editor-tabs" role="tablist" aria-label="Edit studio sections">
          ${/*safe*/editorTabButton('basic', 'Basic info', true)}
          ${/*safe*/editorTabButton('contacts', 'Owner & Contact')}
          ${/*safe*/editorTabButton('admin', 'Admin Login')}
          ${/*safe*/editorTabButton('subscription', 'Subscription & Plan')}
          ${/*safe*/editorTabButton('limits', 'Limits & Works')}
        </div>
        <section id="editor-section-basic" class="form-section editor-panel" role="tabpanel" data-editor-panel="basic" aria-labelledby="editorTab-basic">
          ${/*safe*/editorPanelLead('Basic', `${esc(t.name)} · ${esc(t.slug)}`)}
          <div class="form-section-body form-grid">
            <div class="form-group"><label for="m_tenantName">Studio Name</label><input id="m_tenantName" value="${esc(t.name)}"></div>
            <div class="form-group"><label for="m_tenantSlug">Slug</label><input id="m_tenantSlug" value="${esc(t.slug)}" readonly><small>The studio's public address. It is on flyers and in QR codes, so it is changed on its own, not saved with this form. <button type="button" class="link-button" onclick="openSlugChange('${esc(t.id)}')">Change public address</button></small></div>
            <div class="form-group"><label for="m_tenantCategory">Category</label><select id="m_tenantCategory">${/*safe*/categoryOptions(t.category || 'general')}</select></div>
            <div class="form-group"><label for="m_tenantSlogan">Slogan</label><input id="m_tenantSlogan" value="${esc(t.slogan || presetSlogan(t.category || 'general'))}"></div>
            <div class="form-group">
              <span class="form-label">Tenant Status</span>
              <div class="derived-value">
                <span class="pill ${esc(t.status)}">${esc(t.status)}</span>
                <span class="derived-note">Lifecycle changes are audited and happen in their own flow.</span>
              </div>
              <input id="m_tenantStatus" type="hidden" value="${esc(t.status)}">
            </div>
            <div class="form-group"><label for="m_tenantPlan">Plan</label><select id="m_tenantPlan">${/*safe*/plans.map(p => `<option value="${esc(p.code)}" ${p.code===t.plan_code?'selected':''}>${esc(planDisplayName(p))}</option>`).join('')}</select></div>
            <div id="m_planChangeImpact" class="plan-change-impact" hidden aria-live="polite"></div>
          </div>
        </section>
        <section id="editor-section-contacts" class="form-section editor-panel" role="tabpanel" data-editor-panel="contacts" aria-labelledby="editorTab-contacts" hidden>
          ${/*safe*/editorPanelLead('Owner & Contact', esc(t.owner_email || 'Needs owner'))}
          <div class="form-section-body">
            <div class="form-grid">
              <div class="form-group"><label for="m_ownerName">Owner Name</label><input id="m_ownerName" value="${esc(t.owner_name||'')}"></div>
              <div class="form-group"><label for="m_ownerRole">Owner Role</label><input id="m_ownerRole" value="${esc(t.owner_role||'')}"></div>
              <div class="form-group"><label for="m_ownerEmail">Owner Email</label><input id="m_ownerEmail" type="email" value="${esc(t.owner_email||'')}"></div>
              <div class="form-group"><label for="m_ownerPhone">Owner Phone</label><input id="m_ownerPhone" value="${esc(t.owner_phone||'')}"></div>
              <div class="form-group"><label for="m_contactEmail">Contact Email</label><input id="m_contactEmail" type="email" value="${esc(t.contact_email||'')}"></div>
              <div class="form-group"><label for="m_contactPhone">Contact Phone</label><input id="m_contactPhone" value="${esc(t.contact_phone||'')}"></div>
              <div class="form-group"><label for="m_tenantWebsite">Website</label><input id="m_tenantWebsite" type="url" value="${esc(t.website||'')}"></div>
              <div class="form-group"><label for="m_tenantAbn">ABN</label><input id="m_tenantAbn" value="${esc(t.abn||'')}"></div>
              <div class="form-group" style="grid-column: span 2;"><label for="m_tenantAddress">Address</label><input id="m_tenantAddress" value="${esc(t.address||'')}"></div>
            </div>
            <div class="action-row" style="margin-bottom:12px;">
              <button id="copyOwnerToContactBtn" type="button" class="btn-secondary btn-sm">Use owner email for contact</button>
              <button id="copyOwnerToBillingBtn" type="button" class="btn-secondary btn-sm">Use owner email for billing</button>
              <button id="copyOwnerToAdminBtn" type="button" class="btn-secondary btn-sm">Use owner email for admin login</button>
            </div>
            <div class="form-group"><label for="m_tenantNotes">Notes</label><textarea id="m_tenantNotes" rows="3">${esc(t.notes||'')}</textarea></div>
          </div>
        </section>
        <section id="editor-section-admin" class="form-section editor-panel" role="tabpanel" data-editor-panel="admin" aria-labelledby="editorTab-admin" hidden>
          ${/*safe*/editorPanelLead('Admin Login', t.studio_admin_email ? esc(t.studio_admin_email) : 'Not configured')}
          <div class="form-section-body form-grid">
            <div class="form-group"><label for="m_studioAdminEmail">Studio Admin Email</label><input id="m_studioAdminEmail" type="email" value="${esc(t.studio_admin_email || t.owner_email || '')}"></div>
            <div class="form-group"><label for="m_studioAdminName">Studio Admin Name</label><input id="m_studioAdminName" value="${esc(t.studio_admin_name || t.owner_name || '')}"></div>
            <div class="form-group"><label for="m_loginStatus">Login Status</label><input id="m_loginStatus" value="${/*safe*/t.studio_admin_email ? 'Configured' : 'Not configured'}" disabled></div>
            <div class="form-group"><label for="m_lastLogin">Last Login</label><input id="m_lastLogin" value="${esc(t.studio_admin_last_login ? new Date(t.studio_admin_last_login).toLocaleString() : 'Never logged in')}" disabled></div>
            <div class="form-group"><label for="m_studioAdminPassword">Reset Password</label><input id="m_studioAdminPassword" type="password" placeholder="Leave blank to keep existing password"><small>Leave blank to keep existing password.</small></div>
            <div class="form-group"><label for="m_setupLinkOut">Password Setup Link</label>
              <div style="display:flex;gap:8px;align-items:center;">
                <button type="button" class="btn-secondary btn-sm" onclick="generateSetupLink('${esc(t.id)}')">Generate link</button>
                <input id="m_setupLinkOut" readonly placeholder="One-time link appears here" style="flex:1;">
                <button type="button" class="btn-secondary btn-sm" id="m_setupLinkCopy" style="display:none;" onclick="copySetupLink()">Copy</button>
              </div>
              <small>Single use, expires in 24h. Generating a new link invalidates previous unused ones.</small>
            </div>
          </div>
        </section>
        <section id="editor-section-subscription" class="form-section editor-panel" role="tabpanel" data-editor-panel="subscription" aria-labelledby="editorTab-subscription" hidden>
          ${/*safe*/editorPanelLead('Subscription', `${esc(planDisplayName(tenantPlan(t).code ? tenantPlan(t) : t.plan_code))}${t.current_period_ends_at ? ` · to ${esc(dateOnly(t.current_period_ends_at))}` : ''}`)}
          <div class="form-section-body form-grid">
            <!-- Derived, and it says so as a reading rather than as a
                 disabled text box. A greyed-out input reads as "you should be
                 able to type here and cannot"; a badge reads as a fact. The
                 route that does change it is a link, not a sentence telling
                 the operator to go and find the menu themselves. -->
            <div class="form-group full">
              <span class="form-label">Subscription Status</span>
              <div class="derived-value">
                <span class="pill ${esc(t.subscription_status || '')}">${esc(t.subscription_status || '-')}</span>
                <span class="derived-note">Follows the tenant lifecycle state above.</span>
                <button type="button" class="btn-secondary btn-sm" onclick="closeWorkspaceEditor(); openTenantActions('${esc(t.id)}')">Change tenant status</button>
              </div>
              <input id="m_subscriptionStatus" type="hidden" value="${esc(t.subscription_status || '')}">
            </div>
            ${/*safe*/dateField('m_startsAt', 'Subscription Start', t.starts_at)}
            ${/*safe*/dateField('m_trialEndsAt', 'Trial Ends', t.trial_ends_at)}
            ${/*safe*/dateField('m_currentPeriodEndsAt', 'Current Period Ends', t.current_period_ends_at)}
            ${/*safe*/dateField('m_endsAt', 'Cancellation / Expiry Date', t.ends_at)}
            <div class="form-group"><label for="m_billingEmail">Billing Email</label><input id="m_billingEmail" type="email" value="${esc(t.billing_email||'')}"></div>
            <p class="form-note full" id="m_dateError" role="alert" hidden></p>
          </div>
        </section>
        <section id="editor-section-limits" class="form-section editor-panel" role="tabpanel" data-editor-panel="limits" aria-labelledby="editorTab-limits" hidden>
          ${/*safe*/editorPanelLead('Limits', `<span>Inherited from plan</span> · ${esc(planDisplayName(tenantPlan(t).code ? tenantPlan(t) : t.plan_code))}`)}
          <div class="form-section-body form-grid">
            <div class="form-group"><label for="m_limitStudents">Student Limit</label><input id="m_limitStudents" value="${esc(text(tenantPlan(t).student_limit))}" disabled><small><span>Inherited from plan</span> · ${esc(planDisplayName(tenantPlan(t).code ? tenantPlan(t) : t.plan_code))}</small></div>
            <div class="form-group"><label for="m_limitStorage">Storage Limit</label><input id="m_limitStorage" value="${esc(formatStorageMb(tenantPlan(t).storage_limit_mb))}" disabled><small><span>Inherited from plan</span> · ${esc(planDisplayName(tenantPlan(t).code ? tenantPlan(t) : t.plan_code))}</small></div>
            <div class="form-group"><label for="m_limitUsers">Admin User Limit</label><input id="m_limitUsers" value="${esc(text(tenantPlan(t).user_limit))}" disabled><small><span>Inherited from plan</span> · ${esc(planDisplayName(tenantPlan(t).code ? tenantPlan(t) : t.plan_code))}</small></div>
            <div class="form-group"><label for="m_limitMedia">Media Upload Limit</label><input id="m_limitMedia" value="Canonical media service limits by asset type" disabled></div>
            <div class="form-group"><label for="m_limitShowcase">Published Showcase Works</label><input id="m_limitShowcase" value="${esc(`${text(t.showcase_active_count || 0)} / ${text(tenantPlan(t).showcase_limit || 0)}`)}" disabled><small>Draft and archived works remain stored when a plan changes.</small></div>
          </div>
        </section>
        <p class="form-aside">
          <span>Lifecycle and danger actions remain in the selected tenant Inspector.</span>
        </p>
      `;
	      const footerHtml = `<span class="editor-footer-note">Changes are saved to this tenant only after review.</span><button id="m_saveTenant" onclick="saveTenantModal()" class="btn-primary">Save Changes</button><button onclick="closeWorkspaceEditor()" class="btn-secondary">Cancel</button>`;
	      openWorkspaceEditor({
	        workspace: 'tenants',
	        kind: 'tenant',
	        id,
        title: t.name,
	        subtitle: 'Update studio profile, contact, login and subscription metadata.',
	        bodyHtml: formHtml,
	        footerHtml
	      });
	      // THE call that never existed: editTenant rendered the strip and left
	      // it inert for want of this line, while the only invocation sat in
	      // addPlan(), an editor with no tabs at all.
	      wireEditorTabs(focusSection);
	      // A change on a tab the operator is no longer looking at leaves no
	      // trace, so the tab itself carries the mark.
	      markEditedSections();
	      $('m_tenantPlan').addEventListener('change', () => renderPlanChangeImpact(t));
	      renderPlanChangeImpact(t);
	      // "14 days left" is the reading the operator opened this form for, so
	      // it has to be there before they touch anything.
	      ['m_startsAt', 'm_trialEndsAt', 'm_currentPeriodEndsAt', 'm_endsAt']
	        .forEach(refreshDateHint);
	      $('m_tenantCategory').addEventListener('change', () => {
	        if (!$('m_tenantSlogan').value.trim()) $('m_tenantSlogan').value = presetSlogan($('m_tenantCategory').value);
	      });
      $('copyOwnerToContactBtn').addEventListener('click', () => { $('m_contactEmail').value = $('m_ownerEmail').value.trim(); });
      $('copyOwnerToBillingBtn').addEventListener('click', () => { $('m_billingEmail').value = $('m_ownerEmail').value.trim(); });
      $('copyOwnerToAdminBtn').addEventListener('click', () => {
        $('m_studioAdminEmail').value = $('m_ownerEmail').value.trim();
        if (!$('m_studioAdminName').value.trim()) $('m_studioAdminName').value = $('m_ownerName').value.trim();
      });
	    }

    // Support-mode flow. Tenant-scoped studio-admin/CMS routes 403 with
    // "support_session_required" for a platform super admin without an active
    // support session, so gated links route through this modal and open their
    // target only after the session starts.
    let supportTargetHref = '';

    async function enterSupportMode(tenantId, targetHref = '') {
      const t = tenants.find((item) => item.id === tenantId);
      if (!t) return;
      supportTargetHref = targetHref;
      const targetNote = targetHref
        ? '<p class="text-muted" style="margin-top:8px;">This page requires an active support session. It will open in a new tab after support mode starts.</p>'
        : '';
      openModal(
        `Support ${/*safe*/t.name}`, // title renders via textContent
        `<p>Every support-mode action is audited against this reason.</p>${/*safe*/targetNote}<div class="form-group mt-2"><label for="m_supportReason">Reason</label><textarea id="m_supportReason" aria-required="true" aria-describedby="supportReasonError" rows="4" placeholder="Describe the customer request or incident reference"></textarea><p id="supportReasonError" class="form-note" role="alert" hidden></p></div>`,
        `<button id="confirmSupportModeBtn" onclick="confirmSupportMode('${esc(tenantId)}')" class="btn-primary">Start Support Mode</button><button onclick="closeModal()" class="btn-secondary">Cancel</button>`,
      );
    }

    function setSupportReasonError(message = '') {
      const field = $('m_supportReason');
      const error = $('supportReasonError');
      if (!field || !error) return;
      const hasError = Boolean(message);
      error.hidden = !hasError;
      error.textContent = message;
      if (hasError) field.setAttribute('aria-invalid', 'true');
      else field.removeAttribute('aria-invalid');
      if (hasError) {
        window.AdminI18n?.localise?.(error);
        field.focus();
      }
    }

    async function confirmSupportMode(tenantId) {
      const reason = $('m_supportReason').value.trim();
      if (!reason) {
        setSupportReasonError('A reason is required to enter support mode.');
        showToast('A reason is required to enter support mode.', 'error');
        return;
      }
      setSupportReasonError('');
      $('confirmSupportModeBtn').disabled = true;
      try {
        const data = await api(`/admin/tenants/${tenantId}/support-session`, {
          method: 'POST',
          body: JSON.stringify({ reason }),
        });
        const target = supportTargetHref;
        supportTargetHref = '';
        showToast(target
          ? 'Support mode started — opening the tenant workspace.'
          : 'Support mode started — opening Studio Admin.', 'success');
        closeModal();
        window.open(target || data.url, '_blank');
      } catch (err) {
        $('confirmSupportModeBtn').disabled = false;
        setSupportReasonError(err.status === 403
          ? 'Support mode is not available for this account.'
          : err.message);
      }
    }

    // Button that looks like an action link but starts the support-mode flow
    // before opening a tenant-scoped page (Studio CMS / Brand Workspace).
    function addSupportGatedLink(container, label, tenantId, href, disabledReason = '') {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = `btn-secondary${disabledReason ? ' is-disabled' : ''}`;
      const icon = document.createElement('span');
      icon.className = 'gate-icon';
      icon.setAttribute('aria-hidden', 'true');
      icon.innerHTML = ICON_SHIELD;
      const textEl = document.createElement('span');
      textEl.textContent = label;
      button.append(icon, textEl);
      button.title = disabledReason || 'Opens via Support Mode (audited).';
      if (disabledReason) button.disabled = true;
      else button.addEventListener('click', () => enterSupportMode(tenantId, href));
      container.appendChild(button);
      return button;
    }

    async function generateSetupLink(tenantId) {
      const out = $('m_setupLinkOut');
      out.value = 'Generating…';
      try {
        const data = await api(`/admin/tenants/${tenantId}/password-setup-link`, { method: 'POST', body: '{}' });
        out.value = location.origin + data.url;
        $('m_setupLinkCopy').style.display = '';
        showToast(`Link created for ${data.email} (expires in 24h)`, 'success');
      } catch (err) {
        out.value = '';
      }
    }

    async function copySetupLink() {
      const out = $('m_setupLinkOut');
      try {
        await navigator.clipboard.writeText(out.value);
        showToast('Link copied to clipboard', 'success');
      } catch (err) {
        out.select();
        document.execCommand('copy');
        showToast('Link copied', 'success');
      }
    }

    /* Flag any fold whose fields have been touched since the form opened. */
    function markEditedSections() {
      workspaceEditorRoot().querySelectorAll('.form-section').forEach((section) => {
        section.querySelectorAll('input, select, textarea').forEach((field) => {
          const initial = field.type === 'checkbox' ? field.checked : field.value;
          const check = () => {
            const now = field.type === 'checkbox' ? field.checked : field.value;
            field.dataset.edited = String(now !== initial);
            const touched = Boolean(section.querySelector('[data-edited="true"]'));
            section.classList.toggle('edited', touched);
            if (isWorkspaceEditorOpen() && now !== initial) markWorkspaceEditorDirty();
            refreshEditorTabFlags();
          };
          field.addEventListener('input', check);
          field.addEventListener('change', check);
        });
      });
    }

    async function saveTenantModal() {
      const payload = {
        name: $('m_tenantName').value,
        slug: $('m_tenantSlug').value,
	        status: $('m_tenantStatus').value,
	        planCode: $('m_tenantPlan').value,
	        category: $('m_tenantCategory').value,
	        slogan: $('m_tenantSlogan').value,
	        subscriptionStatus: $('m_subscriptionStatus').value,
        /* All four dates, always. `trialEndsAt` was never sent, and the
           server read it as `payload.get("trialEndsAt")` — absent meant None,
           so every save wrote NULL over `trial_ends_at`, the column the trial
           state and the expiring-trial counter both read from. The server
           now distinguishes absent from null as well; sending the full set
           means this form no longer depends on that distinction. */
        startsAt: $('m_startsAt').value || null,
        trialEndsAt: $('m_trialEndsAt').value || null,
        endsAt: $('m_endsAt').value || null,
        currentPeriodEndsAt: $('m_currentPeriodEndsAt').value || null,
        ownerName: $('m_ownerName').value,
        ownerRole: $('m_ownerRole').value,
        ownerPhone: $('m_ownerPhone').value,
        ownerEmail: $('m_ownerEmail').value,
        studioAdminEmail: $('m_studioAdminEmail').value,
        studioAdminName: $('m_studioAdminName').value,
        studioAdminPassword: $('m_studioAdminPassword').value,
        contactPhone: $('m_contactPhone').value,
        contactEmail: $('m_contactEmail').value,
        billingEmail: $('m_billingEmail').value,
        abn: $('m_tenantAbn').value,
        website: $('m_tenantWebsite').value,
        address: $('m_tenantAddress').value,
        notes: $('m_tenantNotes').value
      };

      const editedTenant = editingTenantId
        ? tenants.find((item) => item.id === editingTenantId)
        : null;
      const planChanged = Boolean(editedTenant && editedTenant.plan_code !== payload.planCode);
      const planChangeAcknowledged = Boolean($('m_planChangeConfirm')?.checked);
      payload.confirmPlanChange = planChangeAcknowledged;
      payload.tenantNotificationAcknowledged = planChangeAcknowledged;

      /* Every refusal below has to move the operator to the field, because a
         tabbed form can put the problem on a page they are not looking at. A
         toast that says "check the subscription dates" while the subscription
         tab is hidden is a dead end. */
      if (!payload.name || !payload.slug) {
        const missing = !payload.name ? 'm_tenantName' : 'm_tenantSlug';
        $(missing)?.setAttribute('aria-invalid', 'true');
        revealEditorProblem(missing);
        showToast('Name and slug are required.', 'error');
        return;
      }
      $('m_tenantName')?.removeAttribute('aria-invalid');
      $('m_tenantSlug')?.removeAttribute('aria-invalid');
      if (planChanged && !planChangeAcknowledged) {
        revealEditorProblem('m_planChangeImpact');
        showToast('Review the plan impact and acknowledge tenant notification before saving.', 'error');
        return;
      }
      if (!validateSubscriptionDates()) {
        // The message is already beside the fields; switching to their tab is
        // what stops it from being an error nobody can see.
        revealEditorProblem('m_dateError');
        showToast('Check the subscription dates.', 'error');
        return;
      }
      refreshEditorTabFlags();

      // Submitting with no visible response is the single highest-severity
      // form rule in the UX set, and this form had none: the button stayed
      // idle for the whole round trip.
      const saveButton = $('m_saveTenant');
      const finish = beginSaving(saveButton);
      $('platformEditWorkspace')?.classList.add('is-submitting');
      setWorkspaceEditorState('Saving…', false);
      try {
        await api(editingTenantId ? `/admin/tenants/${editingTenantId}` : '/admin/tenants', {
          method: editingTenantId ? 'PATCH' : 'POST',
          body: JSON.stringify(payload)
        });
      } catch (error) {
        finish();
        $('platformEditWorkspace')?.classList.remove('is-submitting');
        setWorkspaceEditorState('Save failed', true);
        throw error;
      }
      finish();
      $('platformEditWorkspace')?.classList.remove('is-submitting');
      setWorkspaceEditorState('Saved', false);
      showToast(editingTenantId ? 'Tenant updated.' : 'Tenant created.');
      closeWorkspaceEditor({ confirm: false, focus: false });
      await refresh();
    }

    /* Disable-and-label a submit button for the length of its request, and
       hand back the undo. Returns a function rather than taking a callback so
       the caller's error path is its own business. */
    function beginSaving(button, label = 'Saving…') {
      if (!button) return () => {};
      const original = button.textContent;
      const width = button.getBoundingClientRect().width;
      // Pin the width so the button does not jump as the label changes.
      button.style.minWidth = `${Math.ceil(width)}px`;
      button.disabled = true;
      button.classList.add('btn-loading');
      relabel(button, label);
      return () => {
        button.disabled = false;
        button.classList.remove('btn-loading');
        button.style.minWidth = '';
        relabel(button, original);
      };
    }

    function changeTenantOperationalState(id, action) {
      const t = tenants.find((item) => item.id === id);
      if (!t) return;
      const isPause = action === 'pause';
      const title = isPause ? 'Pause Tenant' : 'Reactivate Tenant';
      const targetStatus = isPause ? 'paused' : 'active';
      const targetSubscription = isPause ? 'paused' : 'active';
      const verb = isPause ? 'Pause' : 'Reactivate';
      const body = isPause
        ? `<p>Pause <strong>${esc(t.name)}</strong>? Public tenant pages stay present, but the tenant will be marked paused for operations and billing review.</p>`
        : `<p>Reactivate <strong>${esc(t.name)}</strong>? This restores active tenant status and subscription state.</p>`;
      const confirm = `<div class="form-group mt-2"><label for="m_tenantStateConfirmSlug">Type tenant slug to confirm</label><input id="m_tenantStateConfirmSlug" placeholder="${esc(t.slug)}"></div>`;
      const footerHtml = `<button id="confirmTenantStateBtn" onclick="confirmTenantState('${esc(id)}', '${/*safe*/targetStatus}', '${/*safe*/targetSubscription}')" class="${/*safe*/isPause ? 'btn-danger' : 'btn-primary'}">${/*safe*/verb}</button><button onclick="closeModal()" class="btn-secondary">Cancel</button>`;
      openModal(title, body + confirm, footerHtml);
    }

    /* Its own dialog rather than a field on the tenant form. An address lives
       on printed material, so the cost of changing it by accident is nothing
       like the cost of a mistyped contact email — and a field that saves with
       everything else is a field that eventually gets changed by accident. */
    function openSlugChange(id) {
      const t = tenants.find((item) => item.id === id);
      if (!t) return;
      const body = `
        <p>${esc(t.name)} is published at <strong>/${esc(t.slug)}</strong>.</p>
        <div class="form-group"><label for="m_newSlug">New public address</label><input id="m_newSlug" placeholder="mellow-pear-studio" data-i18n-lock autocomplete="off"><small>Lowercase letters, numbers and hyphens.</small></div>
        <div class="mt-2">
          <strong>Keeps working</strong>
          <ul>
            <li>The old address redirects to the new one permanently — printed QR codes do not need reprinting.</li>
            <li>Students, courses, work, schedules and media are untouched.</li>
            <li>Signed-in staff are not logged out.</li>
          </ul>
          <strong>What changes</strong>
          <ul>
            <li>Search engines take a few weeks to show the new address.</li>
            <li>Visitors' saved language preference resets once.</li>
            <li>This studio cannot change its address again for a year.</li>
          </ul>
        </div>
        <div class="form-group mt-2"><label for="m_slugConfirm">Type the current address to confirm</label><input id="m_slugConfirm" placeholder="${esc(t.slug)}" data-i18n-lock autocomplete="off"></div>
        <label class="switch-row mt-2"><input id="m_slugNotified" type="checkbox"> <span>I have told this studio</span></label>`;
      const footerHtml = `<button id="confirmSlugBtn" onclick="confirmSlugChange('${esc(id)}')" class="btn-primary">Change address</button><button onclick="closeModal()" class="btn-secondary">Cancel</button>`;
      openModal('Change public address', body, footerHtml);
    }

    async function confirmSlugChange(id) {
      const t = tenants.find((item) => item.id === id);
      if (!t) return;
      const slug = ($('m_newSlug')?.value || '').trim().toLowerCase();
      /* The CURRENT address, not the new one: this step confirms which studio
         is being changed, not whether the operator can type. */
      if (($('m_slugConfirm')?.value || '').trim() !== t.slug) {
        showToast(`Type ${t.slug} to confirm.`, 'error');
        return;
      }
      if (!$('m_slugNotified')?.checked) {
        showToast('Confirm the studio has been told.', 'error');
        return;
      }
      const btn = $('confirmSlugBtn');
      btn.disabled = true;
      try {
        const result = await api(`/admin/tenants/${id}/slug`, {
          method: 'PATCH',
          body: JSON.stringify({
            slug,
            confirmSlugChange: true,
            tenantNotificationAcknowledged: true
          })
        });
        showToast(`Address changed to /${result.slug}. The old one redirects.`);
        closeModal();
        await refresh();
      } catch (error) {
        btn.disabled = false;
      }
    }

    async function confirmTenantState(id, status, subscriptionStatus) {
      const t = tenants.find((item) => item.id === id);
      if (!t) return;
      if (($('m_tenantStateConfirmSlug')?.value || '').trim() !== t.slug) {
        showToast(`Type ${t.slug} to confirm.`, 'error');
        return;
      }
      // Same pattern as confirmSupportMode: re-enable the button on failure so
      // the dialog never dead-locks (api() already shows the error toast).
      const btn = $('confirmTenantStateBtn');
      btn.disabled = true;
      try {
        await api(`/admin/tenants/${id}/status`, {
          method: 'PATCH',
          body: JSON.stringify({ status, subscriptionStatus })
        });
        showToast(status === 'paused' ? 'Tenant paused.' : 'Tenant reactivated.');
        closeModal();
        await refresh();
      } finally {
        btn.disabled = false;
      }
    }

    function openTenantActions(id, anchor = null) {
      const t = tenants.find((item) => item.id === id);
      if (!t) return;
      const unavailable = ['archived', 'deleted'].includes(t.status);
      /* One context key covers both pause and reactivation; the tenant status
         determines the explicit next step shown in the right panel. */
      const lifecycleAction = 'pause';
      openActionMenu({
        title: `${t.name} Actions`,
        subtitle: 'High-frequency tenant actions',
        anchor,
        groups: [
          { title: 'Manage', items: [
            { label: 'View Details', handler: () => openTenantInspector(id) },
            { label: 'Edit Tenant', handler: () => editTenant(id, { focusSection: 'basic' }) },
            { label: 'Subscription & Plan', handler: () => editTenant(id, { focusSection: 'subscription', actionContext: 'plan' }) },
            { label: 'View Audit History', handler: () => openTenantActionContext(id, 'audit') },
          ] },
          { title: 'Open', items: [
            { label: 'Open Studio Website', handler: () => openTenantActionContext(id, 'website'), disabled: unavailable },
            { label: 'Open CMS', handler: () => openTenantActionContext(id, 'cms'), disabled: unavailable },
            { label: 'Open Studio Admin', handler: () => openTenantActionContext(id, 'studio-admin'), disabled: unavailable },
            { label: 'Open Quick Registration', handler: () => openTenantActionContext(id, 'register'), disabled: ['paused', 'archived', 'deleted'].includes(t.status) },
          ] },
          { title: 'Support Mode', items: [
            { label: 'Enter Support Mode', handler: () => openTenantActionContext(id, 'support'), disabled: unavailable },
          ] },
          { title: 'Status', items: [
            { label: t.status === 'paused' ? 'Reactivate tenant' : 'Pause tenant', handler: () => openTenantActionContext(id, lifecycleAction), disabled: unavailable || t.status === 'deleted', danger: t.status !== 'paused' },
            { label: t.status === 'archived' ? 'Restore tenant' : 'Archive tenant', handler: () => openTenantActionContext(id, 'archive'), disabled: t.status === 'deleted', danger: t.status !== 'archived' },
          ] },
          { title: 'Danger Zone', items: [
            { label: 'Permanent delete tenant', handler: () => openTenantActionContext(id, 'delete'), disabled: t.status !== 'archived', danger: true },
          ] },
          /* Only rendered for a tenant the SERVER has marked as a
             demonstration. Not disabled-but-visible: an operator who can see
             "Reset demonstration data" on a real studio's menu is one careless
             click from wiping it, and no confirmation dialog undoes a habit. */
          ...(t.is_demo ? [{ title: 'Demonstration', items: [
            { label: 'Reset demonstration data', handler: () => resetDemoTenant(id), danger: true },
          ] }] : []),
        ],
      });
    }

    function openPlanActions(code, anchor = null) {
      const plan = plans.find((item) => item.code === code);
      if (!plan) return;
      const assigned = tenants.filter((item) => item.plan_code === plan.code).length;
      openActionMenu({
        title: `${planDisplayName(plan)} Actions`,
        subtitle: 'High-frequency plan actions',
        anchor,
        groups: [
          { title: 'Manage', items: [
            { label: 'View Details', handler: () => openPlanInspector(plan) },
            { label: 'Edit Plan', handler: () => editPlan(plan.code) },
            { label: 'View tenants on this plan', handler: () => openPlanActionContext(plan.code, 'tenants') },
          ] },
          { title: 'Danger Zone', items: [
            { label: 'Delete Plan', handler: () => openPlanActionContext(plan.code, 'delete'), disabled: Boolean(assigned), danger: true },
          ] },
        ],
      });
    }

    /* Kept as a named helper so future plan actions can use the same right
       context contract as tenants without reopening a centered modal. */
    function openPlanActionContext(code, actionKey, { focus = true } = {}) {
      const plan = plans.find((item) => item.code === code);
      if (!plan) return;
      inspectorMode = 'plan-action';
      inspectorSelection = code;
      inspectorActionKey = actionKey;
      selectedTenantId = '';
      openInspector();
      const body = $('workspaceInspectorBody');
      body.replaceChildren();
      setInspectorHeader('Action context', actionKey === 'delete' ? 'Delete Plan' : 'Plan tenants');
      const section = inspectorSection(actionKey === 'delete' ? 'Danger Zone' : 'Plan usage', 'Review before action');
      const note = document.createElement('div');
      note.className = `action-context-note${actionKey === 'delete' ? ' inspector-support' : ''}`;
      relabel(note, actionKey === 'delete'
        ? 'Deleting a plan is allowed only when no tenant is assigned to it.'
        : 'Select this plan in the tenant workspace to review assigned studios and their current usage.');
      section.appendChild(note);
      body.appendChild(section);
      const actions = inspectorSection('Action', 'Explicit confirmation');
      const list = document.createElement('div');
      list.className = 'inspector-action-list';
      if (actionKey === 'delete') {
        inspectorAction(list, 'Delete Plan', () => deletePlan(code), 'inspector-action inspector-support');
      } else {
        inspectorAction(list, 'Filter tenants by this plan', () => {
          history.pushState(null, '', '#tenants');
          setActiveWorkspace('tenants');
          if ($('planFilter')) $('planFilter').value = code;
          tenantPage = 0;
          renderTenants();
        });
      }
      actions.appendChild(list);
      body.appendChild(actions);
      document.querySelectorAll('tr[data-plan-code]').forEach((row) => row.classList.toggle('is-inspector-selected', row.dataset.planCode === String(code)));
      window.AdminI18n?.localise?.(body);
      if (focus && window.matchMedia('(max-width: 1279px)').matches) $('workspaceInspector')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    /* Re-seed the demonstration tenant from showcase_content.py and
       seed-assets/showcase/manifest.json. Everything the tenant holds is
       replaced; nothing outside it is touched. The phrase is the same one the
       command-line script demands, so there is one thing to remember. */
    function resetDemoTenant(id) {
      const t = tenants.find((item) => item.id === id);
      if (!t) return;
      if (!t.is_demo) { showToast('This tenant is not a demonstration tenant.', 'error'); return; }
      const footerHtml = `<button id="confirmDemoResetBtn" onclick="confirmDemoReset('${esc(id)}')" class="btn-danger">Reset demonstration data</button><button onclick="closeModal()" class="btn-secondary">Cancel</button>`;
      openModal('Reset Demonstration Data', `<p>Rebuild <strong>${esc(t.name)}</strong> from the bundled demonstration content.</p><ul style="margin:12px 0 12px 20px;color:var(--muted);"><li>Students, schedules, bookings and enquiries are deleted and re-created</li><li>Uploaded media for this tenant is deleted and re-uploaded from the manifest</li><li>Staff logins are reset to the shared demonstration password</li><li>The student access code is rotated</li></ul><p style="color:var(--muted)">No other tenant is read or written. This takes a few seconds.</p><div class="form-group mt-2"><label for="m_demoResetPhrase">Type the confirmation phrase</label><small><code>RESET-LETS-PAINT-SHOWCASE</code></small><input id="m_demoResetPhrase" placeholder="RESET-LETS-PAINT-SHOWCASE" data-i18n-lock autocomplete="off"></div>`, footerHtml);
    }

    async function confirmDemoReset(id) {
      const phrase = ($('m_demoResetPhrase')?.value || '').trim();
      const btn = $('confirmDemoResetBtn');
      btn.disabled = true;
      // It runs for several seconds; without this the button looks broken and
      // gets pressed again.
      const restore = btn.textContent;
      btn.textContent = 'Rebuilding…';
      try {
        const result = await api(`/admin/tenants/${id}/demo-reset`, {
          method: 'POST',
          body: JSON.stringify({ confirm: phrase }),
        });
        showToast(`Demonstration rebuilt in ${result.seconds}s — ${result.studioWorks} works, ${result.publicStudentWorks}/${result.studentWorks} student works public, ${result.students} students.`);
        closeModal();
        await refresh();
      } finally {
        btn.disabled = false;
        btn.textContent = restore;
      }
    }

    function archiveTenant(id) {
      const t = tenants.find((item) => item.id === id);
      if (!t) return;
      const footerHtml = `<button id="confirmArchiveTenantBtn" onclick="confirmArchiveTenant('${esc(id)}')" class="btn-danger">Archive Tenant</button><button onclick="closeModal()" class="btn-secondary">Cancel</button>`;
      openModal('Archive Tenant', `<p>Archive <strong>${esc(t.name)}</strong>? Tenant APIs become unavailable after snapshots are written.</p><ul style="margin:12px 0 12px 20px;color:var(--muted);"><li>Database snapshot</li><li>Workspace folder copy</li><li>Media folder copy</li><li>Subscription metadata</li></ul><div class="form-group mt-2"><label for="m_archiveTenantConfirmSlug">Type tenant slug to confirm</label><input id="m_archiveTenantConfirmSlug" placeholder="${esc(t.slug)}"></div>`, footerHtml);
    }

    async function confirmArchiveTenant(id) {
      const t = tenants.find((item) => item.id === id);
      if (!t) return;
      if (($('m_archiveTenantConfirmSlug')?.value || '').trim() !== t.slug) {
        showToast(`Type ${t.slug} to confirm.`, 'error');
        return;
      }
      const btn = $('confirmArchiveTenantBtn');
      btn.disabled = true;
      try {
        const result = await api(`/admin/tenants/${id}/archive`, { method: 'POST' });
        showToast(`Tenant archived. Snapshot: ${result.archivePath || 'created'}`);
        closeModal();
        await refresh();
      } finally {
        btn.disabled = false;
      }
    }

    async function restoreTenant(id) {
      const t = tenants.find((item) => item.id === id);
      if (!t) return;
      await api(`/admin/tenants/${id}/restore`, { method: 'POST' });
      showToast('Tenant restored to paused status.');
      closeModal();
      await refresh();
    }

    function permanentDeleteTenant(id) {
      const t = tenants.find((item) => item.id === id);
      if (!t) return;
      const footerHtml = `<button id="confirmPermanentDeleteTenantBtn" onclick="confirmPermanentDeleteTenant('${esc(id)}')" class="btn-danger">Permanent Delete</button><button onclick="closeModal()" class="btn-secondary">Cancel</button>`;
      openModal('Permanent Delete Tenant', `<p>Permanently delete <strong>${esc(t.name)}</strong>? This is irreversible for live tenant records.</p><ul style="margin:12px 0 12px 20px;color:var(--muted);"><li>Final snapshot path: ${esc(t.archive_path || 'archive/final-delete-snapshot')}</li><li>Tenant database records</li><li>Archived files remain as audit evidence</li><li>Media records are removed by tenant deletion</li></ul><div class="form-group mt-2"><label for="m_permanentDeleteTenantPhrase">Type DELETE ${esc(t.slug)} to confirm</label><input id="m_permanentDeleteTenantPhrase" placeholder="DELETE ${esc(t.slug)}" data-i18n-lock></div>`, footerHtml);
    }

    async function confirmPermanentDeleteTenant(id) {
      const t = tenants.find((item) => item.id === id);
      if (!t) return;
      const phrase = ($('m_permanentDeleteTenantPhrase')?.value || '').trim();
      if (phrase !== `DELETE ${t.slug}`) {
        showToast(`Type DELETE ${t.slug} to confirm.`, 'error');
        return;
      }
      const btn = $('confirmPermanentDeleteTenantBtn');
      btn.disabled = true;
      try {
        await api(`/admin/tenants/${id}/permanent`, {
          method: 'DELETE',
          body: JSON.stringify({ confirmationPhrase: phrase })
        });
        showToast('Tenant permanently deleted. Archive evidence was retained.');
        closeModal();
        await refresh();
      } finally {
        btn.disabled = false;
      }
    }

    // Select tenant to view details
    function selectTenant(id) {
      openTenantInspector(id);
    }

    /* The tenant detail view.
     *
     * It used to be one flat wall of twenty-five cards, and seven of the
     * fields appeared TWICE — a `tenant-summary` block and a `detail-grid`
     * were both rendered, and they overlapped on studio, status,
     * subscription, plan, category, student usage, storage and owner email.
     * Nothing about reading the code made that visible; it took a screenshot
     * of the running modal.
     *
     * Now: a status bar that never scrolls out of the way, and five tabs.
     * Tabs rather than folds because this is a reading surface — an operator
     * opens it already knowing which kind of question they have, and wants to
     * jump, not to unfold in sequence. The bar stays outside the tabs because
     * health and quota are what you want visible no matter which one you are
     * looking at.
     */
    const TENANT_DETAIL_TABS = [
      ['overview', 'Overview'],
      ['subscription', 'Subscription & Billing'],
      ['contacts', 'Contacts'],
      ['usage', 'Usage'],
      ['operations', 'Operations'],
    ];

    function buildTenantDetailGrid(t) {
      const plan = plans.find((item) => item.code === t.plan_code) || {};
      const container = document.createElement('div');
      const slug = encodeURIComponent(String(t.slug || ''));

      /* ── the bar: four readings, always on screen ──────────────────── */
      const bar = document.createElement('div');
      bar.className = 'detail-bar';
      const barItem = (label, build) => {
        const cell = document.createElement('div');
        const labelEl = document.createElement('div');
        labelEl.className = 'detail-bar-label';
        labelEl.textContent = label;
        cell.className = 'detail-bar-item';
        cell.appendChild(labelEl);
        build(cell);
        bar.appendChild(cell);
      };
      barItem('Health', (cell) => appendHealthPill(cell, t));
      barItem('Plan', (cell) => {
        const value = document.createElement('div');
        value.className = 'detail-bar-value';
        value.textContent = planDisplayName(plan.code ? plan : t.plan_code);
        cell.appendChild(value);
      });
      barItem('Students', (cell) => appendBarQuota(cell, t.student_count, plan.student_limit));
      barItem('Storage', (cell) => appendBarQuota(
        cell, t.storage_used_mb, plan.storage_limit_mb, formatStorageMb));
      container.appendChild(bar);

      /* ── tabs ─────────────────────────────────────────────────────── */
      const strip = document.createElement('div');
      strip.className = 'tab-strip';
      strip.setAttribute('role', 'tablist');
      strip.setAttribute('aria-label', 'Tenant detail sections');
      window.AdminI18n?.localise?.(strip);
      const panels = document.createElement('div');
      const built = {};

      TENANT_DETAIL_TABS.forEach(([key, label], index) => {
        const tab = document.createElement('button');
        tab.type = 'button';
        tab.className = 'tab';
        tab.id = `tenantTab_${key}`;
        tab.textContent = label;
        tab.setAttribute('role', 'tab');
        tab.setAttribute('aria-controls', `tenantPanel_${key}`);
        tab.setAttribute('aria-selected', String(index === 0));
        tab.tabIndex = index === 0 ? 0 : -1;

        const panel = document.createElement('div');
        panel.className = 'tab-panel';
        panel.id = `tenantPanel_${key}`;
        panel.setAttribute('role', 'tabpanel');
        panel.setAttribute('aria-labelledby', tab.id);
        panel.hidden = index !== 0;
        built[key] = panel;

        const select = () => {
          strip.querySelectorAll('.tab').forEach((el) => {
            el.setAttribute('aria-selected', String(el === tab));
            el.tabIndex = el === tab ? 0 : -1;
          });
          Object.entries(built).forEach(([panelKey, el]) => { el.hidden = panelKey !== key; });
        };
        tab.addEventListener('click', select);
        // Left/right move between tabs, which is what a tablist owes a
        // keyboard user; without it the arrow keys do nothing and Tab walks
        // into panels the reader cannot see.
        tab.addEventListener('keydown', (event) => {
          const order = TENANT_DETAIL_TABS.map(([k]) => k);
          const at = order.indexOf(key);
          let next = null;
          if (event.key === 'ArrowRight') next = order[(at + 1) % order.length];
          if (event.key === 'ArrowLeft') next = order[(at - 1 + order.length) % order.length];
          if (event.key === 'Home') next = order[0];
          if (event.key === 'End') next = order[order.length - 1];
          if (!next) return;
          event.preventDefault();
          const target = strip.querySelector(`#tenantTab_${next}`);
          target.click();
          target.focus();
        });
        strip.appendChild(tab);
        panels.appendChild(panel);
      });
      container.append(strip, panels);

      const card = (panel, label, build) => {
        const item = document.createElement('div');
        const labelEl = document.createElement('div');
        item.className = 'detail-item';
        labelEl.className = 'detail-label';
        labelEl.textContent = label;
        item.appendChild(labelEl);
        build(item);
        panel.appendChild(item);
        return item;
      };
      const grid = (panel, split = false) => {
        const wrap = document.createElement('div');
        wrap.className = split ? 'detail-grid detail-split' : 'detail-grid';
        panel.appendChild(wrap);
        return wrap;
      };

      /* ── 1 · Overview: what to do about this tenant ────────────────── */
      // 61.8 / 38.2 — the checklist is the argument, the links are the
      // standing offer, same division the marketing pages use.
      const overview = grid(built.overview, true);
      const overviewMain = document.createElement('div');
      const overviewSide = document.createElement('div');
      overview.append(overviewMain, overviewSide);

      card(overviewMain, 'Risk / Setup', (item) => {
        const risks = tenantRisks(t);
        if (!risks.length) {
          appendPillWithIcon(item, 'Healthy', 'pill active', PILL_CHECK);
          return;
        }
        const list = document.createElement('div');
        list.className = 'risk-list';
        risks.forEach((risk) => {
          const row = document.createElement('div');
          row.className = 'risk-item';
          row.textContent = risk;
          list.appendChild(row);
        });
        item.appendChild(list);
      });
      card(overviewMain, 'Onboarding Checklist', (item) => {
        const progress = document.createElement('div');
        progress.className = 'detail-value';
        progress.textContent = onboardingProgress(t);
        item.appendChild(progress);
        onboardingChecklist(t).forEach(([label, complete]) => {
          const row = document.createElement('div');
          const markEl = document.createElement('span');
          markEl.setAttribute('aria-hidden', 'true');
          markEl.textContent = complete ? '✓ ' : '○ ';
          row.append(markEl, document.createTextNode(label));
          row.className = complete ? 'check-row done' : 'check-row';
          item.appendChild(row);
        });
      });
      card(overviewSide, 'Quick Links', (item) => {
        const links = document.createElement('div');
        links.className = 'link-grid';
        const unavailable = ['archived', 'deleted'].includes(t.status);
        addActionLink(links, 'Studio Website', `/${slug}`, unavailable ? 'Archived or deleted tenants cannot be opened.' : '');
        addSupportGatedLink(links, 'Studio CMS', t.id, `/${slug}/cms`, unavailable ? 'Archived or deleted tenants cannot be opened.' : '');
        addSupportGatedLink(links, 'Brand Workspace', t.id, `/${slug}/studio-admin`, unavailable ? 'Archived or deleted tenants cannot be opened.' : '');
        addActionLink(links, 'Quick Registration', `/${slug}/register`, ['paused', 'archived', 'deleted'].includes(t.status) ? 'Registration is unavailable for paused, archived, or deleted tenants.' : '');
        item.appendChild(links);
      });
      card(overviewSide, 'Studio', (item) => {
        const strong = document.createElement('strong');
        const code = document.createElement('code');
        strong.textContent = text(t.name);
        code.textContent = text(t.slug);
        item.append(strong, document.createElement('br'), code);
        const category = document.createElement('div');
        category.className = 'detail-sub';
        category.textContent = `${text(t.category || 'general')}${t.slogan ? ` · ${t.slogan}` : ''}`;
        item.appendChild(category);
      });

      /* ── 2 · Subscription & billing ────────────────────────────────── */
      const subscription = grid(built.subscription);
      card(subscription, 'Status', (item) => {
        const rows = [
          ['Tenant', () => appendPill(item, t.status)],
          ['Subscription', () => appendPill(item, t.subscription_status || '-')],
          ['Access', () => appendSmallBadge(item, accessStatus(t), accessStatus(t) === 'Enabled' ? 'pill active' : 'pill')],
        ];
        rows.forEach(([label, build], index) => {
          if (index) item.appendChild(document.createElement('br'));
          item.appendChild(document.createTextNode(`${label}: `));
          build();
        });
      });
      card(subscription, 'Plan', (item) => addStrongMuted(
        item, planDisplayName(plan.code ? plan : t.plan_code), plan.monthly_price_aud != null ? money(plan.monthly_price_aud) : ''));
      card(subscription, 'Subscription Period', (item) => {
        appendDateRow(item, 'Start', t.starts_at, { deadline: false });
        appendDateRow(item, 'Trial ends', t.trial_ends_at);
        appendDateRow(item, 'Current period ends', t.current_period_ends_at);
        appendDateRow(item, 'Cancellation / expiry', t.ends_at, { emptyLabel: 'Open-ended' });
      });
      card(subscription, 'Billing', (item) => {
        item.append(document.createTextNode(text(t.billing_email)),
                    document.createElement('br'),
                    document.createTextNode(`ABN ${text(t.abn)}`));
      });

      /* ── 3 · Contacts ──────────────────────────────────────────────── */
      const contacts = grid(built.contacts);
      card(contacts, 'Owner', (item) => addStrongMuted(item, t.owner_name, t.owner_email));
      card(contacts, 'Studio Admin Login', (item) => addStrongMuted(item, t.studio_admin_email, t.studio_admin_name));
      card(contacts, 'Contact', (item) => {
        item.append(document.createTextNode(text(t.contact_phone)),
                    document.createElement('br'),
                    document.createTextNode(text(t.contact_email)));
      });

      /* ── 4 · Usage ─────────────────────────────────────────────────── */
      const usage = grid(built.usage);
      card(usage, 'Students', (item) => addProgressRow(item, t.student_count, plan.student_limit));
      card(usage, 'Storage', (item) => addProgressRow(item, t.storage_used_mb, plan.storage_limit_mb, formatStorageMb));
      card(usage, 'Team Users', (item) => addProgressRow(item, t.user_count, plan.user_limit));

      /* ── 5 · Operations ────────────────────────────────────────────── */
      const operations = grid(built.operations);
      card(operations, 'Workspace', (item) => {
        const code = document.createElement('code');
        code.textContent = text(t.workspace_path);
        item.appendChild(code);
      });
      card(operations, 'Created', (item) => appendDateValue(item, t.created_at));
      if (t.status === 'archived') {
        card(operations, 'Archived', (item) => appendDateValue(item, t.archived_at));
        card(operations, 'Archive Path', (item) => {
          const code = document.createElement('code');
          code.textContent = text(t.archive_path);
          item.appendChild(code);
        });
      }
      return container;
    }

    /* One quota reading, one shape. The bar and the Usage tab both call this
       family so a figure cannot be written two ways in one modal — the old
       code had the summary going through `formatStorageMb` (20 MB / 50 GB)
       while the progress bar below it printed raw megabytes (20 / 51200). */
    function quotaParts(current, limit, format = (v) => text(v)) {
      const used = Number(current || 0);
      const cap = Number(limit || 0);
      return { used, cap, pct: percent(used, cap), label: cap ? `${format(used)} / ${format(cap)}` : format(used) };
    }

    function quotaTone(pct) {
      return pct > 90 ? 'red' : pct > 75 ? 'amber' : 'blue';
    }

    function appendBarQuota(cell, current, limit, format) {
      const { pct, label } = quotaParts(current, limit, format);
      const value = document.createElement('div');
      value.className = 'detail-bar-value tabular';
      value.textContent = label;
      const bar = document.createElement('div');
      const fill = document.createElement('div');
      bar.className = 'progress-bar';
      fill.className = `progress-fill ${quotaTone(pct)}`;
      fill.style.width = `${pct}%`;
      bar.appendChild(fill);
      cell.append(value, bar);
    }

    function addProgressRow(item, current, limit, format) {
      const { pct, label } = quotaParts(current, limit, format);
      const top = document.createElement('div');
      const left = document.createElement('span');
      const right = document.createElement('span');
      const bar = document.createElement('div');
      const fill = document.createElement('div');
      top.className = 'progress-head tabular';
      left.textContent = label;
      right.textContent = `${pct}%`;
      bar.className = 'progress-bar';
      fill.className = `progress-fill ${quotaTone(pct)}`;
      fill.style.width = `${pct}%`;
      top.append(left, right);
      bar.appendChild(fill);
      item.append(top, bar);
    }

    /* A date, plus how far away it is. "2027-01-01" answers a question nobody
       asked; "in 150 days" is the thing the operator was actually looking
       for, and an expired one has to be impossible to read past. */
    function relativeDays(value) {
      const iso = dateOnly(value);
      if (!iso) return null;
      const then = new Date(`${iso}T00:00:00Z`);
      const now = new Date();
      const today = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate());
      return Math.round((then.getTime() - today) / 86400000);
    }

    function appendDateValue(item, value) {
      const iso = dateOnly(value);
      const span = document.createElement('span');
      span.className = 'tabular';
      span.textContent = iso || '-';
      item.appendChild(span);
    }

    /* A date row, and how far away the date is.

       Only a DEADLINE can be overdue. A subscription start in the past is the
       ordinary case — it is what "this has begun" looks like — and marking it
       red told the operator that every healthy studio needed attention. The
       distinction lives in `SUBSCRIPTION_DEADLINES` on the server and is
       mirrored by the `deadline` flag here. */
    function appendDateRow(item, label, value, { emptyLabel = '—', deadline = true } = {}) {
      const iso = dateOnly(value);
      const row = document.createElement('div');
      const name = document.createElement('span');
      const val = document.createElement('span');
      row.className = 'date-row';
      name.className = 'date-row-label';
      name.textContent = label;
      val.className = 'date-row-value tabular';
      val.textContent = iso || emptyLabel;
      row.append(name, val);
      const days = iso === '' ? null : relativeDays(value);
      if (days !== null) {
        row.appendChild(dateRelativeBadge(days, deadline));
      }
      item.appendChild(row);
    }

    /* The badge, and the one place that decides what a number of days means.
       A past deadline is a problem; a past start is history; a near deadline
       is a warning. Written as a number plus a translatable word, because an
       interpolated "3 days left" matches nothing in the dictionary. */
    function dateRelativeBadge(days, deadline) {
      const badge = document.createElement('span');
      let tone = '';
      let word;
      if (days < 0) {
        word = deadline ? 'days overdue' : 'days ago';
        tone = deadline ? 'overdue' : '';
      } else {
        word = 'days left';
        tone = deadline && days <= 14 ? 'soon' : '';
      }
      badge.className = tone ? `date-rel ${tone}` : 'date-rel';
      badge.append(document.createTextNode(`${Math.abs(days)} `));
      const unit = document.createElement('span');
      unit.textContent = word;
      badge.appendChild(unit);
      return badge;
    }

    function openTenantDetailModal(id) {
      const t = tenants.find((item) => item.id === id);
      if (!t) return;
      openModal(`${/*safe*/t.name} Details`, '<div id="m_tenantDetailMount"></div>', '<button onclick="closeModal()" class="btn-secondary">Close</button>'); // title renders via textContent
      $('modalOverlay').classList.add('detail-overlay');
      $('modalOverlay').querySelector('.modal').classList.add('detail-modal');
      $('m_tenantDetailMount').replaceChildren(buildTenantDetailGrid(t));
    }

    // Filter tenants
    function filteredTenants() {
      const q = $('tenantSearch').value.trim().toLowerCase();
      const status = $('statusFilter').value;
      const plan = $('planFilter').value;
      const category = $('categoryFilter').value;
      const showTests = $('showTestTenants')?.checked || false;
      const metric = METRIC_FILTERS[metricFilter];
      return tenants.filter((t) => {
	        const haystack = `${t.name} ${t.slug} ${t.status} ${t.plan_code} ${t.subscription_status || ''} ${t.category || ''} ${t.owner_email || ''} ${t.studio_admin_email || ''}`.toLowerCase();
        return (!metric || metric.match(t)) && (showTests || !isTestTenant(t)) && (!q || haystack.includes(q)) && (!status || t.status === status) && (!plan || t.plan_code === plan) && (!category || (t.category || 'general') === category);
      });
    }

    /* Re-translate one label the page just rewrote. Deliberately per-node
       rather than over the whole card: the dictionary matches any text it
       recognises, and a studio actually named "Overview" would be turned into
       总览 by a subtree walk over the tenants table. */
    const relabel = (el, value) => {
      el.textContent = value;
      window.AdminI18n?.localise?.(el);
    };

    /* One place decides what the metric filter is, so the chip, the pressed
       counters and the table can never describe different things. */
    function setMetricFilter(key) {
      metricFilter = METRIC_FILTERS[key] ? key : '';
      const active = METRIC_FILTERS[metricFilter];
      document.querySelectorAll('.stats-grid button.stat-card[data-metric]').forEach((card) => {
        card.setAttribute('aria-pressed', String(card.dataset.metric === metricFilter));
      });
      $('metricFilterRow').classList.toggle('hidden', !active);
      if (active) {
        /* Write the English label and let the dictionary translate it in
           place, exactly as it does for the counter it came from. Writing the
           translation directly would strand the chip in Chinese when the
           operator switches back — localise() remembers the original, a
           hand-translated string has no original to restore. */
        relabel($('metricFilterLabel'), active.label);
      }
      tenantPage = 0;
      renderTenants();
    }

    // Render tenants table
    function renderTenants() {
      const allVisible = filteredTenants();
      const totalPages = Math.max(1, Math.ceil(allVisible.length / tenantPageSize));
      if (tenantPage >= totalPages) tenantPage = totalPages - 1;
      const visible = allVisible.slice(tenantPage * tenantPageSize, (tenantPage + 1) * tenantPageSize);
      relabel($('tenantPageLabel'), `Page ${tenantPage + 1} of ${totalPages} · ${allVisible.length} tenants`);
      $('tenantPrevBtn').disabled = tenantPage <= 0;
      $('tenantNextBtn').disabled = tenantPage >= totalPages - 1;
      const tbody = $('tenantsBody');
      tbody.replaceChildren();
      if (!visible.length) {
        appendEmptyRow(tbody, 6, 'No tenants match the current filters.');
        return;
      }
      visible.forEach((t) => {
        const row = document.createElement('tr');
        row.dataset.tenantId = String(t.id);
        row.classList.toggle('is-inspector-selected', selectedTenantId === t.id);
        wireQuickViewRow(row, () => openTenantInspector(t.id), `View ${text(t.name)}`);
        const studioCell = addCell(row, '', 'Studio');
        const strong = document.createElement('strong');
        const code = document.createElement('code');
        const muted = document.createElement('span');
        strong.textContent = text(t.name);
        code.textContent = text(t.slug);
        muted.className = 'text-muted';
        muted.textContent = `${text(t.category || 'general')} · ${text(t.studio_admin_email || 'no admin login')}`;
        studioCell.append(strong, document.createElement('br'), code, document.createElement('br'), muted);
        if (isTestTenant(t)) {
          studioCell.appendChild(document.createElement('br'));
          appendSmallBadge(studioCell, 'TEST FIXTURE', 'pill fixture');
        }
        addStrongMuted(addCell(row, '', 'Plan'), planDisplayName(tenantPlan(t).code ? tenantPlan(t) : t.plan_code), t.category || 'general');
        /* Three stacked pills in a narrow column wrapped their labels onto
           three lines each, and a pill's radius turned "Needs setup" into an
           amber disc. One primary pill and one secondary line, neither
           allowed to wrap; health is only shown when it is not "Healthy",
           because a column of green ticks is a column carrying no
           information. */
        const statusCell = addCell(row, '', 'Status');
        statusCell.className += ' status-cell';
        appendPill(statusCell, t.status);
        const sub = document.createElement('div');
        sub.className = 'status-sub';
        sub.textContent = text(t.subscription_status || '-');
        statusCell.appendChild(sub);
        if (healthLabel(t) !== 'Healthy') appendHealthPill(statusCell, t);
        const ownerCell = addCell(row, '', 'Owner');
        const ownerLine = document.createElement('div');
        ownerLine.className = 'ellipsis';
        ownerLine.textContent = t.owner_email || 'Needs owner';
        // The full address on hover: the column truncates, and an operator
        // who needs to read one should not have to open the tenant.
        if (t.owner_email) ownerLine.title = t.owner_email;
        ownerCell.appendChild(ownerLine);
        if (!t.owner_email) appendSmallBadge(ownerCell, 'Needs owner', 'pill warning');
        if (!t.studio_admin_email) appendSmallBadge(ownerCell, 'No admin login', 'pill warning');
        renderUsageCell(addCell(row, '', 'Usage'), t);
        const actions = document.createElement('div');
        actions.className = 'action-row';
        addActionButton(actions, 'Actions', 'btn-secondary btn-sm', (button) => openTenantActions(t.id, button));
        addCell(row, '', 'Actions').appendChild(actions);
        tbody.appendChild(row);
      });
      window.AdminI18n?.localise?.(tbody);
    }

    /* Usage as two hairline bars rather than a sentence.
       `0 / 100 students · 0 MB / 2.0 GB` had to be read to be understood, and
       the one thing this column exists to answer — who is close to a limit —
       was the thing it made hardest. The figures stay, under the bars. */
    function renderUsageCell(cell, t) {
      const plan = tenantPlan(t);
      const wrap = document.createElement('div');
      wrap.className = 'usage-cell';
      [['Students', t.student_count, plan.student_limit, undefined],
       ['Storage', t.storage_used_mb, plan.storage_limit_mb, formatStorageMb],
       ['Showcase works', t.showcase_active_count, plan.showcase_limit, undefined],
      ].forEach(([label, current, limit, format]) => {
        const { pct, label: figure } = quotaParts(current, limit, format);
        const line = document.createElement('div');
        const name = document.createElement('span');
        const value = document.createElement('span');
        const bar = document.createElement('div');
        const fill = document.createElement('div');
        line.className = 'usage-line';
        name.textContent = label;
        value.className = 'tabular';
        value.textContent = figure;
        bar.className = 'progress-bar';
        fill.className = `progress-fill ${quotaTone(pct)}`;
        fill.style.width = `${pct}%`;
        // The bar is decoration over a number that is already there, so it is
        // hidden from assistive tech rather than announced twice.
        bar.setAttribute('aria-hidden', 'true');
        line.append(name, value);
        bar.appendChild(fill);
        wrap.append(line, bar);
      });
      cell.appendChild(wrap);
    }

    /* Subscriptions whose dates have already passed.

       Everything here was invisible before this release — the product had no
       code that compared a subscription date to today, so a trial could lapse
       and a cancellation date could go by with the console showing green. */
    function openSettlement() {
      if (!settlement) {
        showToast('Subscription dates are unavailable. Refresh and try again.', 'error');
        return;
      }
      const findings = settlement.findings || [];
      const actionable = findings.filter((f) => f.category === 'actionable' && f.target);
      const footer = actionable.length
        ? `<button id="m_applySettlement" onclick="applySettlement()" class="btn-primary">Apply ${actionable.length} change${actionable.length === 1 ? '' : 's'}</button><button onclick="closeModal()" class="btn-secondary">Close</button>`
        : '<button onclick="closeModal()" class="btn-secondary">Close</button>';
      openModal('Subscription dates that have passed', '<div id="m_settlementMount"></div>', footer);
      $('m_settlementMount').replaceChildren(buildSettlementList(findings));
    }

    const SETTLEMENT_TONE = { actionable: 'pill warning', review: 'pill', data: 'pill' };

    function buildSettlementList(findings) {
      const wrap = document.createElement('div');
      if (!findings.length) {
        const done = document.createElement('p');
        done.className = 'settlement-empty';
        done.textContent = 'No subscription has passed a date it should not have.';
        wrap.appendChild(done);
        return wrap;
      }
      const note = document.createElement('p');
      note.className = 'settlement-note';
      note.textContent = 'Nothing here has been changed. Applying moves only the rows marked Automatic; a lapsed trial is always a decision for a person.';
      wrap.appendChild(note);

      findings.forEach((f) => {
        const row = document.createElement('div');
        row.className = 'settlement-row';
        const head = document.createElement('div');
        head.className = 'settlement-head';
        const name = document.createElement('strong');
        name.textContent = f.tenant_name || f.slug;
        head.appendChild(name);
        const tone = document.createElement('span');
        tone.className = SETTLEMENT_TONE[f.category] || 'pill';
        tone.textContent = f.target ? 'Automatic' : f.category === 'data' ? 'Data' : 'Decide';
        head.appendChild(tone);
        if (f.days !== null && f.days !== undefined) {
          const days = document.createElement('span');
          days.className = 'date-rel overdue';
          days.append(document.createTextNode(`${f.days} `));
          const word = document.createElement('span');
          word.textContent = 'days overdue';
          days.appendChild(word);
          head.appendChild(days);
        }
        const summary = document.createElement('p');
        summary.className = 'settlement-summary';
        summary.textContent = f.summary;
        row.append(head, summary);
        if (f.target) {
          const move = document.createElement('p');
          move.className = 'settlement-move';
          move.append(document.createTextNode(`${f.tenant_status} → `));
          const to = document.createElement('strong');
          to.textContent = f.target[0];
          move.appendChild(to);
          row.appendChild(move);
        }
        wrap.appendChild(row);
      });
      return wrap;
    }

    async function applySettlement() {
      const button = $('m_applySettlement');
      const finish = beginSaving(button, 'Applying…');
      try {
        const result = await api('/admin/subscriptions/settlement/apply', {
          method: 'POST',
          headers: { 'X-Requested-With': 'StudioSaaS' },
          body: JSON.stringify({ apply: true })
        });
        finish();
        showToast(`${(result.changed || []).length} subscriptions settled.`, 'success');
        closeModal();
        await refresh();
      } catch (error) {
        finish();
      }
    }

    // Plan form handlers
    const KNOWN_PLAN_FEATURES = [
      ['public_registration', 'Public registration'],
      ['portfolio', 'Student portfolio'],
      ['email_templates', 'Email templates'],
      ['data_export', 'Data export'],
      ['priority_support', 'Priority support']
    ];

    function planFeatureLabel(key) {
      return KNOWN_PLAN_FEATURES.find(([candidate]) => candidate === key)?.[1] || key;
    }

    function planImpactValue(field, value) {
      if (field === 'monthly_price_aud') return money(value);
      if (field === 'storage_limit_mb') return formatStorageMb(value);
      if (field === 'is_public') return value ? 'Published' : 'Not published';
      return Number(value || 0).toLocaleString();
    }

    function tenantPlanChangeDetails(tenant, targetPlan) {
      const currentPlan = tenantPlan(tenant);
      if (!tenant || !targetPlan || !currentPlan.code || currentPlan.code === targetPlan.code) return null;
      const limitFields = [
        ['monthly_price_aud', 'Monthly price'],
        ['student_limit', 'Students'],
        ['user_limit', 'Team users'],
        ['storage_limit_mb', 'Storage'],
        ['showcase_limit', 'Showcase works published'],
      ];
      const changed = limitFields
        .filter(([field]) => Number(currentPlan[field]) !== Number(targetPlan[field]))
        .map(([field, label]) => ({
          field,
          label,
          from: planImpactValue(field, currentPlan[field]),
          to: planImpactValue(field, targetPlan[field]),
          reduced: Number(targetPlan[field]) < Number(currentPlan[field]),
        }));
      if (Boolean(currentPlan.is_public) !== Boolean(targetPlan.is_public)) {
        changed.push({
          field: 'is_public',
          label: 'Public pricing page',
          from: planImpactValue('is_public', currentPlan.is_public),
          to: planImpactValue('is_public', targetPlan.is_public),
          reduced: Boolean(currentPlan.is_public) && !targetPlan.is_public,
        });
      }
      const currentFeatures = currentPlan.features || {};
      const targetFeatures = targetPlan.features || {};
      const featureKeys = [...new Set([...Object.keys(currentFeatures), ...Object.keys(targetFeatures)])].sort();
      const enabledFeatures = featureKeys.filter((key) => !currentFeatures[key] && targetFeatures[key]);
      const disabledFeatures = featureKeys.filter((key) => currentFeatures[key] && !targetFeatures[key]);
      const usageOver = [
        ['Students', tenant.student_count, targetPlan.student_limit, 'student_count'],
        ['Team users', tenant.user_count, targetPlan.user_limit, 'user_count'],
        ['Storage', tenant.storage_used_mb, targetPlan.storage_limit_mb, 'storage_used_mb'],
        ['Showcase works', tenant.showcase_active_count, targetPlan.showcase_limit, 'showcase_active_count'],
      ].filter(([, current, limit]) => Number(limit || 0) > 0 && Number(current || 0) > Number(limit || 0))
        .map(([label, current, limit, field]) => ({ label, current, limit, field }));
      return {
        currentPlan,
        targetPlan,
        changed,
        enabledFeatures,
        disabledFeatures,
        usageOver,
        isDowngrade: changed.some((item) => item.reduced) || disabledFeatures.length > 0,
      };
    }

    function appendPlanImpactBullet(list, label, value = '') {
      const item = document.createElement('li');
      const labelEl = document.createElement('span');
      relabel(labelEl, label);
      item.appendChild(labelEl);
      if (value) {
        const valueEl = document.createElement('span');
        valueEl.className = 'plan-impact-value';
        valueEl.textContent = value;
        item.append(' · ', valueEl);
      }
      list.appendChild(item);
      return item;
    }

    function appendPlanImpactGroup(grid, title, items) {
      const group = document.createElement('div');
      group.className = 'plan-impact-group';
      const heading = document.createElement('strong');
      relabel(heading, title);
      group.appendChild(heading);
      const list = document.createElement('ul');
      list.className = 'plan-impact-list';
      if (!items.length) {
        const empty = document.createElement('li');
        empty.className = 'plan-impact-empty';
        relabel(empty, 'No additional change identified.');
        list.appendChild(empty);
      } else {
        items.forEach((item) => appendPlanImpactBullet(list, item.label, item.value || ''));
      }
      group.appendChild(list);
      grid.appendChild(group);
      return group;
    }

    function renderPlanChangeImpact(tenant) {
      const mount = $('m_planChangeImpact');
      if (!mount) return;
      const acknowledged = Boolean($('m_planChangeConfirm')?.checked);
      mount.replaceChildren();
      mount.hidden = true;
      const target = plans.find((item) => item.code === $('m_tenantPlan')?.value);
      const impact = tenantPlanChangeDetails(tenant, target);
      if (!impact) return;
      mount.hidden = false;
      mount.classList.toggle('is-danger', impact.isDowngrade || impact.usageOver.length > 0);
      const heading = document.createElement('strong');
      relabel(heading, 'Plan change review');
      mount.appendChild(heading);
      const route = document.createElement('div');
      route.className = 'text-muted';
      const from = document.createElement('span');
      from.textContent = planDisplayName(impact.currentPlan);
      const arrow = document.createTextNode(' → ');
      const to = document.createElement('span');
      to.textContent = planDisplayName(impact.targetPlan);
      route.append(from, arrow, to);
      mount.appendChild(route);

      const grid = document.createElement('div');
      grid.className = 'plan-impact-grid';
      appendPlanImpactGroup(grid, 'Will change', impact.changed.map((item) => ({
        label: item.label,
        value: `${item.from} → ${item.to}`,
      })).concat(
        impact.enabledFeatures.map((key) => ({ label: 'Feature enabled', value: planFeatureLabel(key) })),
        impact.disabledFeatures.map((key) => ({ label: 'Feature disabled', value: planFeatureLabel(key) })),
      ));
      appendPlanImpactGroup(grid, 'Will be preserved', [
        { label: 'Website, brand and showcase content' },
        { label: 'Students, courses, registrations and media' },
        { label: 'Audit history and tenant settings' },
      ]);
      const notify = [
        { label: 'Plan, price and effective date' },
        { label: 'New resource and showcase limits' },
      ];
      if (impact.disabledFeatures.length) {
        notify.push({ label: 'Feature availability', value: impact.disabledFeatures.map(planFeatureLabel).join(', ') });
      }
      if (impact.usageOver.length) {
        notify.push({ label: 'Current usage is above the new limit', value: impact.usageOver.map((item) => `${item.label} ${item.current} / ${item.limit}`).join(', ') });
      }
      appendPlanImpactGroup(grid, 'Notify tenant', notify);
      mount.appendChild(grid);

      const ack = document.createElement('label');
      ack.className = 'feature-row plan-impact-ack';
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.id = 'm_planChangeConfirm';
      checkbox.checked = acknowledged;
      checkbox.addEventListener('change', markWorkspaceEditorDirty);
      const copy = document.createElement('span');
      const label = document.createElement('span');
      label.className = 'feature-label';
      relabel(label, 'I reviewed the impact and will notify this tenant.');
      const note = document.createElement('span');
      note.className = 'feature-note';
      relabel(note, 'The server will reject the plan change without this acknowledgement.');
      copy.append(label, note);
      ack.append(checkbox, copy);
      mount.appendChild(ack);
      window.AdminI18n?.localise?.(mount);
      renderEditorInspector();
    }

    function planFormSnapshot() {
      let features = {};
      try {
        features = JSON.parse($('m_planFeaturesAdvanced')?.value || '{}');
      } catch {
        features = {};
      }
      document.querySelectorAll('[data-plan-feature]').forEach((input) => {
        features[input.dataset.planFeature] = input.checked;
      });
      return {
        code: editingPlanCode,
        name: $('m_planName')?.value || '',
        monthly_price_aud: Number($('m_planMonthly')?.value || 0),
        student_limit: Number($('m_planStudents')?.value || 0),
        user_limit: Number($('m_planUsers')?.value || 0),
        storage_limit_mb: gbToMb($('m_planStorage')?.value || 0),
        showcase_limit: Number($('m_planShowcase')?.value || 0),
        features,
        is_public: Boolean($('m_planPublic')?.checked),
        is_recommended: Boolean($('m_planRecommended')?.checked),
      };
    }

    function renderPlanCatalogImpact(plan) {
      const mount = $('m_planCatalogImpact');
      if (!mount || !plan) return;
      mount.replaceChildren();
      mount.hidden = true;
      const draft = planFormSnapshot();
      const changed = [
        ['name', 'Plan name'],
        ['monthly_price_aud', 'Monthly price'],
        ['student_limit', 'Students'],
        ['user_limit', 'Team users'],
        ['storage_limit_mb', 'Storage'],
        ['showcase_limit', 'Showcase works published'],
        ['is_public', 'Public pricing page'],
      ].filter(([field]) => {
        const before = field === 'name' ? plan.name : field === 'is_public' ? Boolean(plan.is_public) : Number(plan[field]);
        const after = field === 'name' ? draft.name : field === 'is_public' ? draft.is_public : Number(draft[field]);
        return before !== after;
      }).map(([field, label]) => {
        const before = field === 'name' ? plan.name : planImpactValue(field, plan[field]);
        const after = field === 'name' ? draft.name : planImpactValue(field, draft[field]);
        return { field, label, value: `${before} → ${after}` };
      });
      const currentFeatures = plan.features || {};
      const featureKeys = [...new Set([...Object.keys(currentFeatures), ...Object.keys(draft.features)])].sort();
      const disabledFeatures = featureKeys.filter((key) => currentFeatures[key] && !draft.features[key]);
      const enabledFeatures = featureKeys.filter((key) => !currentFeatures[key] && draft.features[key]);
      const affected = tenants.filter((item) => item.plan_code === plan.code);
      const hasImpact = changed.length || enabledFeatures.length || disabledFeatures.length;
      if (!hasImpact || !affected.length) return;
      mount.hidden = false;
      const heading = document.createElement('strong');
      relabel(heading, 'Plan catalog change review');
      mount.appendChild(heading);
      const intro = document.createElement('p');
      intro.className = 'text-muted';
      relabel(intro, 'This change affects every tenant currently using this plan.');
      mount.appendChild(intro);
      const grid = document.createElement('div');
      grid.className = 'plan-impact-grid';
      appendPlanImpactGroup(grid, 'Will change', changed.concat(
        enabledFeatures.map((key) => ({ label: 'Feature enabled', value: planFeatureLabel(key) })),
        disabledFeatures.map((key) => ({ label: 'Feature disabled', value: planFeatureLabel(key) })),
      ));
      appendPlanImpactGroup(grid, 'Will be preserved', [
        { label: 'Tenant settings and public content' },
        { label: 'Students, courses, registrations and media' },
        { label: 'Audit history' },
      ]);
      appendPlanImpactGroup(grid, 'Notify tenants', [
        { label: 'Affected tenants', value: affected.map((item) => item.name || item.slug).join(', ') },
        { label: 'New price, limits and feature availability' },
      ]);
      mount.appendChild(grid);
      const ack = document.createElement('label');
      ack.className = 'feature-row plan-impact-ack';
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.id = 'm_planCatalogConfirm';
      checkbox.addEventListener('change', markWorkspaceEditorDirty);
      const copy = document.createElement('span');
      const label = document.createElement('span');
      label.className = 'feature-label';
      relabel(label, 'I reviewed the impact and will notify all affected tenants.');
      const note = document.createElement('span');
      note.className = 'feature-note';
      relabel(note, 'The server will reject the plan update without this acknowledgement.');
      copy.append(label, note);
      ack.append(checkbox, copy);
      mount.appendChild(ack);
      window.AdminI18n?.localise?.(mount);
    }

    /* Entitlements, grouped by who feels them.
       Five unexplained switches in one box asked the operator to remember
       what "Priority support" commits us to; the group tells them who it is
       for and the line under each says what it turns on. */
    const PLAN_FEATURE_GROUPS = [
      ['What the studio can publish', [
        ['public_registration', 'Public registration', 'Families can apply from the studio website without being invited.'],
        ['portfolio', 'Student portfolio', 'Student work can be published with recorded guardian consent.'],
      ]],
      ['What the studio can send and take away', [
        ['email_templates', 'Email templates', 'Reusable message templates in the operations CMS.'],
        ['data_export', 'Data export', 'Students, credits and attendance can be exported as a spreadsheet.'],
      ]],
      ['What we commit to', [
        ['priority_support', 'Priority support', 'Ahead of the standard queue. This is a commitment we have to staff.'],
      ]],
    ];

    function planFeatureEditor(features = {}) {
      const known = new Set(PLAN_FEATURE_GROUPS.flatMap(([, rows]) => rows.map(([key]) => key)));
      const additional = Object.fromEntries(
        Object.entries(features || {}).filter(([key]) => !known.has(key)));
      const groups = PLAN_FEATURE_GROUPS.map(([heading, rows]) => `
        <div class="feature-group">
          <p class="feature-group-title">${heading}</p>
          ${rows.map(([key, label, note]) => `
            <label class="feature-row">
              <input type="checkbox" data-plan-feature="${key}" ${features[key] ? 'checked' : ''}>
              <span><span class="feature-label">${label}</span>
              <span class="feature-note">${note}</span></span>
            </label>`).join('')}
        </div>`).join('');
      /* The JSON box stays — a flag added to the database tomorrow has to be
         reachable before this list knows about it — but it validates as you
         type now. It used to accept anything and throw on save, after the
         operator had already left the field. */
      return `
        <fieldset class="form-section plan-fieldset">
          <legend>Entitlements</legend>
          ${groups}
          <details class="advanced-json">
            <summary>Flags not listed above<span class="summary-hint">${Object.keys(additional).length ? `${Object.keys(additional).length} set` : 'none'}</span></summary>
            <label for="m_planFeaturesAdvanced">Additional entitlements (JSON)</label>
            <textarea id="m_planFeaturesAdvanced" rows="3" oninput="validatePlanJson()">${esc(JSON.stringify(additional, null, 2))}</textarea>
            <small class="date-hint" id="m_planFeaturesAdvanced_hint"></small>
          </details>
        </fieldset>
      `;
    }

    const PLAN_VALIDATION_FIELDS = ['m_planCode', 'm_planName', 'm_planMonthly', 'm_planStudents', 'm_planUsers', 'm_planStorage', 'm_planShowcase'];

    function preparePlanValidation() {
      PLAN_VALIDATION_FIELDS.forEach((id) => {
        const field = $(id);
        if (!field || $(`${id}Error`)) return;
        const error = document.createElement('small');
        error.id = `${id}Error`;
        error.className = 'field-error';
        error.hidden = true;
        error.setAttribute('role', 'alert');
        field.setAttribute('aria-describedby', error.id);
        field.parentElement?.appendChild(error);
        field.addEventListener('input', () => setPlanFieldError(id, ''));
      });
    }

    function setPlanFieldError(id, message = '') {
      const field = $(id);
      const error = $(`${id}Error`);
      if (!field || !error) return;
      error.hidden = !message;
      error.textContent = message;
      if (message) field.setAttribute('aria-invalid', 'true');
      else field.removeAttribute('aria-invalid');
      if (message) window.AdminI18n?.localise?.(error);
      if (isWorkspaceEditorOpen()) renderEditorInspector();
    }

    function validatePlanFields() {
      const value = (id) => $(id)?.value.trim() || '';
      const checks = [
        ['m_planCode', !editingPlanCode && !value('m_planCode') ? 'Plan code is required.' : ''],
        ['m_planCode', value('m_planCode') && !/^[a-z0-9][a-z0-9-]{1,62}$/.test(value('m_planCode')) ? 'Plan code must be lowercase letters, numbers, or hyphens.' : ''],
        ['m_planName', !value('m_planName') ? 'Plan name is required.' : ''],
        ['m_planMonthly', !value('m_planMonthly') || !Number.isInteger(Number(value('m_planMonthly'))) || Number(value('m_planMonthly')) < 0 ? 'Monthly price must be a non-negative integer.' : ''],
        ['m_planStudents', !value('m_planStudents') || !Number.isInteger(Number(value('m_planStudents'))) || Number(value('m_planStudents')) <= 0 ? 'Student limit must be a positive integer.' : ''],
        ['m_planUsers', !value('m_planUsers') || !Number.isInteger(Number(value('m_planUsers'))) || Number(value('m_planUsers')) <= 0 ? 'User limit must be a positive integer.' : ''],
        ['m_planStorage', !value('m_planStorage') || Number(value('m_planStorage')) <= 0 ? 'Storage limit must be positive.' : ''],
        ['m_planShowcase', !value('m_planShowcase') || !Number.isInteger(Number(value('m_planShowcase'))) || Number(value('m_planShowcase')) <= 0 ? 'Showcase limit must be a positive integer.' : ''],
      ];
      let firstError = null;
      PLAN_VALIDATION_FIELDS.forEach((id) => setPlanFieldError(id, ''));
      checks.forEach(([id, message]) => {
        if (!message || $(`${id}Error`)?.textContent) return;
        setPlanFieldError(id, message);
        if (!firstError) firstError = $(id);
      });
      if (firstError) firstError.focus();
      return !firstError;
    }

    function validatePlanJson() {
      const field = $('m_planFeaturesAdvanced');
      const hint = $('m_planFeaturesAdvanced_hint');
      if (!field || !hint) return true;
      const raw = field.value.trim();
      let ok = true;
      if (raw) {
        try {
          const parsed = JSON.parse(raw);
          ok = parsed !== null && typeof parsed === 'object' && !Array.isArray(parsed);
        } catch { ok = false; }
      }
      hint.className = ok ? 'date-hint' : 'date-hint overdue';
      relabel(hint, ok ? '' : 'Must be a JSON object, for example {"beta_reports": true}');
      field.setAttribute('aria-invalid', String(!ok));
      if (isWorkspaceEditorOpen()) renderEditorInspector();
      return ok;
    }

    // Publication is not the same decision as definition: a plan exists as
    // soon as it is created, but it only appears on the public pricing page
    // when somebody says it is for sale. Before migration 0023 the two were
    // the same act, and a fixture plan reached the public grid at A$1.
    function planPublicationEditor(plan = {}) {
      /* This block sits at the TOP of the form now. It was at the bottom,
         below the entitlements and the JSON box — and it is the only thing on
         this page that changes what the public website says the moment it is
         saved. The live line underneath shows the row a visitor would read,
         because a checkbox called "Publish" does not tell you what gets
         published. */
      return `
        <fieldset class="form-section plan-fieldset publish-fieldset">
          <legend>Public pricing page</legend>
          <label class="feature-row">
            <input type="checkbox" id="m_planPublic" ${plan.is_public ? 'checked' : ''} onchange="refreshPlanPreview()">
            <span><span class="feature-label">Publish on pwestudio.online</span>
            <span class="feature-note">Off by default. A plan exists as soon as it is created; it is for sale only when somebody says so.</span></span>
          </label>
          <label class="feature-row">
            <input type="checkbox" id="m_planRecommended" ${plan.is_recommended ? 'checked' : ''} onchange="refreshPlanPreview()">
            <span><span class="feature-label">Mark as the recommended plan</span>
            <span class="feature-note">Only one plan carries the badge; ticking it here clears it elsewhere.</span></span>
          </label>
          <div class="plan-preview" id="m_planPreview" aria-live="polite"></div>
        </fieldset>
      `;
    }

    /* What the pricing grid would render, from the values in this form. */
    function refreshPlanPreview() {
      const box = $('m_planPreview');
      if (!box) return;
      box.replaceChildren();
      if (!$('m_planPublic')?.checked) {
        const off = document.createElement('span');
        off.className = 'plan-preview-off';
        off.textContent = 'Not shown on the public pricing page.';
        box.appendChild(off);
        window.AdminI18n?.localise?.(box);
        return;
      }
      const name = $('m_planName')?.value || $('m_planCode')?.value || '';
      const price = Number($('m_planMonthly')?.value || 0);
      const students = Number($('m_planStudents')?.value || 0);
      const users = Number($('m_planUsers')?.value || 0);
      const storage = formatStorageMb(gbToMb($('m_planStorage')?.value));
      const showcase = Number($('m_planShowcase')?.value || 0);
      const head = document.createElement('div');
      head.className = 'plan-preview-head';
      head.textContent = `${name} — A$${price}/month`;
      if ($('m_planRecommended')?.checked) {
        const badge = document.createElement('span');
        badge.className = 'pill active';
        badge.textContent = 'Recommended';
        head.appendChild(badge);
      }
      const list = document.createElement('div');
      list.className = 'plan-preview-list';
      [['Students', students.toLocaleString()], ['Team users', String(users)], ['Storage', storage], ['Showcase works published', showcase.toLocaleString()]]
        .forEach(([label, value]) => {
          const row = document.createElement('div');
          const name_ = document.createElement('span');
          const val = document.createElement('span');
          relabel(name_, label);
          val.className = 'tabular';
          val.textContent = value;
          row.append(name_, val);
          list.appendChild(row);
        });
      box.append(head, list);
      window.AdminI18n?.localise?.(box);
    }

    function collectPlanFeatures() {
      let additional;
      try { additional = JSON.parse($('m_planFeaturesAdvanced').value || '{}'); }
      catch { throw new Error('Additional entitlements must be valid JSON.'); }
      document.querySelectorAll('[data-plan-feature]').forEach((input) => { additional[input.dataset.planFeature] = input.checked; });
      return additional;
    }

    function enabledPlanFeatures(plan) {
      return KNOWN_PLAN_FEATURES.filter(([key]) => Boolean((plan.features || {})[key])).map(([, label]) => label);
    }

    // Plans-table quota cell. Each limit and each entitlement is its own text
    // node — a single "500 students\n8 users\n…" blob can never match the
    // admin-i18n dictionary, so the Chinese UI kept showing English here.
    function renderPlanQuota(cell, plan) {
      const quota = document.createElement('div');
      quota.className = 'plan-quota';
      [
        ['Students', Number(plan.student_limit || 0).toLocaleString()],
        ['Team users', Number(plan.user_limit || 0).toLocaleString()],
        ['Storage', formatStorageMb(plan.storage_limit_mb)],
        ['Showcase works published', Number(plan.showcase_limit || 0).toLocaleString()],
      ].forEach(([label, value]) => {
        const row = document.createElement('div');
        const labelEl = document.createElement('span');
        relabel(labelEl, label);
        row.append(labelEl, document.createTextNode(` ${value}`));
        quota.appendChild(row);
      });
      const features = document.createElement('div');
      features.className = 'plan-features';
      const enabled = enabledPlanFeatures(plan);
      if (enabled.length) {
        enabled.forEach((label, index) => {
          if (index) features.appendChild(document.createTextNode(' · '));
          const item = document.createElement('span');
          item.textContent = label;
          features.appendChild(item);
        });
      } else {
        features.textContent = 'No enabled entitlements';
      }
      quota.appendChild(features);
      cell.appendChild(quota);
    }

    function resetPlanForm() {
      editingPlanCode = '';
      const bodyHtml = `
        ${/*safe*/planPublicationEditor()}
        <div class="form-grid">
          <div class="form-group"><label for="m_planCode">Code</label><input id="m_planCode" placeholder="e.g. studio-pro" data-i18n-lock pattern="[a-z0-9][a-z0-9-]{1,62}"></div>
          <div class="form-group"><label for="m_planName">Name</label><input id="m_planName" oninput="refreshPlanPreview()"></div>
          <div class="form-group"><label for="m_planMonthly">Price (AUD)</label><input id="m_planMonthly" type="number" value="149" oninput="refreshPlanPreview()"></div>
          <div class="form-group"><label for="m_planStudents">Students</label><input id="m_planStudents" type="number" min="1" value="800" oninput="refreshPlanPreview()"></div>
          <div class="form-group"><label for="m_planUsers">Users</label><input id="m_planUsers" type="number" min="1" value="12" oninput="refreshPlanPreview()"></div>
          <div class="form-group"><label for="m_planStorage">Storage (GB)</label><input id="m_planStorage" type="number" min="1" step="0.5" value="50" oninput="refreshPlanPreview()"></div>
          <div class="form-group"><label for="m_planShowcase">Showcase works published</label><input id="m_planShowcase" type="number" min="1" value="15" oninput="refreshPlanPreview()"><small>Active works visible on the public showcase. Drafts and archived works remain stored.</small></div>
        </div>
        ${/*safe*/planFeatureEditor({ public_registration: true, portfolio: true })}
      `;
      const editorFooter = `<span class="editor-footer-note">New plans stay private until Publish is selected.</span><button id="m_savePlan" onclick="savePlanModal()" class="btn-primary">Save Plan</button><button onclick="closeWorkspaceEditor()" class="btn-secondary">Cancel</button>`;
      openWorkspaceEditor({
        workspace: 'plans',
        kind: 'plan',
        title: 'Add Plan',
        subtitle: 'Define limits and publication state before creating a plan.',
        bodyHtml,
        footerHtml: editorFooter
      });
      preparePlanValidation();
      refreshPlanPreview();
    }

    function editPlan(code) {
      const p = plans.find((item) => item.code === code);
      if (!p) return;
      editingPlanCode = code;
      const bodyHtml = `
        ${/*safe*/planPublicationEditor(p)}
        <div class="form-grid">
          <div class="form-group"><label for="m_planCode">Code</label><input id="m_planCode" value="${esc(p.code)}" disabled></div>
          <div class="form-group"><label for="m_planName">Name</label><input id="m_planName" value="${esc(p.name)}" oninput="refreshPlanPreview()"></div>
          <div class="form-group"><label for="m_planMonthly">Price (AUD)</label><input id="m_planMonthly" type="number" value="${esc(p.monthly_price_aud)}" oninput="refreshPlanPreview()"></div>
          <div class="form-group"><label for="m_planStudents">Students</label><input id="m_planStudents" type="number" min="1" value="${esc(p.student_limit)}" oninput="refreshPlanPreview()"></div>
          <div class="form-group"><label for="m_planUsers">Users</label><input id="m_planUsers" type="number" min="1" value="${esc(p.user_limit)}" oninput="refreshPlanPreview()"></div>
          <div class="form-group"><label for="m_planStorage">Storage (GB)</label><input id="m_planStorage" type="number" min="1" step="0.5" value="${esc(mbToGb(p.storage_limit_mb))}" oninput="refreshPlanPreview()"><small>Stored in megabytes; <span class="tabular">${esc(p.storage_limit_mb)}</span> MB today.</small></div>
          <div class="form-group"><label for="m_planShowcase">Showcase works published</label><input id="m_planShowcase" type="number" min="1" value="${esc(p.showcase_limit || 15)}" oninput="refreshPlanPreview()"><small>Active works visible on the public showcase. Drafts and archived works remain stored.</small></div>
        </div>
        <div id="m_planCatalogImpact" class="plan-change-impact" hidden aria-live="polite"></div>
        ${/*safe*/planFeatureEditor(p.features || {})}
      `;
      const footerHtml = `<span class="editor-footer-note">Review affected tenants before saving limits.</span><button id="m_savePlan" onclick="savePlanModal()" class="btn-primary">Save Plan</button><button onclick="closeWorkspaceEditor()" class="btn-secondary">Cancel</button>`;
      openWorkspaceEditor({
        workspace: 'plans',
        kind: 'plan',
        id: code,
        title: planDisplayName(p),
        subtitle: 'Update pricing, limits, entitlements, and publication state.',
        bodyHtml,
        footerHtml
      });
      preparePlanValidation();
      refreshPlanPreview();
      ['m_planName', 'm_planMonthly', 'm_planStudents', 'm_planUsers', 'm_planStorage', 'm_planShowcase', 'm_planPublic', 'm_planRecommended', 'm_planFeaturesAdvanced']
        .forEach((id) => {
          $(id)?.addEventListener('input', () => renderPlanCatalogImpact(p));
          $(id)?.addEventListener('change', () => renderPlanCatalogImpact(p));
        });
      document.querySelectorAll('[data-plan-feature]').forEach((input) => input.addEventListener('change', () => renderPlanCatalogImpact(p)));
      renderPlanCatalogImpact(p);
    }

    /* Megabytes on the wire, gigabytes in front of a person. `51200` is not a
       number anyone can check at a glance, and the field it was typed into
       had no unit beyond a label. */
    function mbToGb(mb) {
      const value = Number(mb || 0) / 1024;
      return Number.isInteger(value) ? String(value) : value.toFixed(1);
    }

    function gbToMb(gb) {
      return Math.round(Number(gb || 0) * 1024);
    }

    async function savePlanModal() {
      if (!validatePlanFields()) return;
      if (!validatePlanJson()) {
        showToast('Additional entitlements must be a JSON object.', 'error');
        $('m_planFeaturesAdvanced').focus();
        return;
      }
      let features;
      try { features = collectPlanFeatures(); }
      catch (error) { showToast(error.message, 'error'); return; }
      const code = $('m_planCode').value.trim().toLowerCase();
      if (!editingPlanCode && !/^[a-z0-9][a-z0-9-]{1,62}$/.test(code)) {
        showToast('Plan code must be lowercase letters, numbers, or hyphens.', 'error');
        $('m_planCode').focus();
        return;
      }
      const payload = {
        code,
        name: $('m_planName').value,
        monthlyPriceAud: Number($('m_planMonthly').value),
        studentLimit: Number($('m_planStudents').value),
        userLimit: Number($('m_planUsers').value),
        storageLimitMb: gbToMb($('m_planStorage').value),
        showcaseLimit: Number($('m_planShowcase').value),
        features,
        isPublic: $('m_planPublic').checked,
        isRecommended: $('m_planRecommended').checked
      };
      /* A limit is not a number on a form, it is a number every studio on
         this plan is held to from the moment Save is pressed. Editing one
         used to be silent about that. */
      const affected = tenants.filter((item) => item.plan_code === editingPlanCode);
      const previousPlan = plans.find((item) => item.code === editingPlanCode);
      const previousFeatures = previousPlan?.features || {};
      const featureKeys = [...new Set([...Object.keys(previousFeatures), ...Object.keys(features)])];
      const featureChanged = featureKeys.some((key) => Boolean(previousFeatures[key]) !== Boolean(features[key]));
      const planDefinitionChanged = Boolean(previousPlan && (
        previousPlan.name !== payload.name
        || Number(previousPlan.monthly_price_aud) !== payload.monthlyPriceAud
        || Number(previousPlan.student_limit) !== payload.studentLimit
        || Number(previousPlan.user_limit) !== payload.userLimit
        || Number(previousPlan.storage_limit_mb) !== payload.storageLimitMb
        || Number(previousPlan.showcase_limit) !== payload.showcaseLimit
        || Boolean(previousPlan.is_public) !== payload.isPublic
        || featureChanged
      ));
      const catalogAcknowledged = Boolean($('m_planCatalogConfirm')?.checked);
      payload.confirmPlanChange = catalogAcknowledged;
      payload.tenantNotificationAcknowledged = catalogAcknowledged;
      if (editingPlanCode && affected.length && planDefinitionChanged && !catalogAcknowledged) {
        $('m_planCatalogImpact')?.scrollIntoView({ block: 'center' });
        showToast('Review the plan impact and acknowledge tenant notification before saving.', 'error');
        return;
      }
      const showcaseReduced = Boolean(
        previousPlan && payload.showcaseLimit < Number(previousPlan.showcase_limit || 0)
      );
      if (editingPlanCode && affected.length) {
        const over = affected.filter((item) =>
          Number(item.student_count || 0) > payload.studentLimit
          || Number(item.storage_used_mb || 0) > payload.storageLimitMb);
        if ((over.length || showcaseReduced)
            && !window.confirm(planImpactWarning(affected.length, over, showcaseReduced))) return;
      }
      const saveButton = $('m_savePlan');
      const finish = beginSaving(saveButton);
      $('platformEditWorkspace')?.classList.add('is-submitting');
      setWorkspaceEditorState('Saving…', false);
      try {
        await api(editingPlanCode ? `/plans/${editingPlanCode}` : '/plans', {
          method: editingPlanCode ? 'PATCH' : 'POST',
          body: JSON.stringify(payload)
        });
      } catch (error) {
        finish();
        $('platformEditWorkspace')?.classList.remove('is-submitting');
        setWorkspaceEditorState('Save failed', true);
        throw error;
      }
      finish();
      $('platformEditWorkspace')?.classList.remove('is-submitting');
      setWorkspaceEditorState('Saved', false);
      showToast(editingPlanCode ? 'Plan updated.' : 'Plan created.');
      closeWorkspaceEditor({ confirm: false, focus: false });
      await refresh();
    }

    function planImpactWarning(total, over, showcaseReduced = false) {
      const names = over.slice(0, 3).map((item) => item.name).join(', ');
      const more = over.length > 3 ? ` (+${over.length - 3})` : '';
      const resourceWarning = over.length
        ? `${over.length} would be over the student/storage limit immediately: ${names}${more}.`
        : '';
      const showcaseWarning = showcaseReduced
        ? 'Lowering showcase works published may hide active works until the plan is raised again.'
        : '';
      return `${total} studios are on this plan. ${resourceWarning} ${showcaseWarning} Save anyway?`.trim();
    }

    async function deletePlan(code) {
      const footerHtml = `<button onclick="confirmDeletePlan('${esc(code)}')" class="btn-danger">Delete</button><button onclick="closeModal()" class="btn-secondary">Cancel</button>`;
      openModal('Delete Plan', `<p>Are you sure you want to delete plan <strong>${esc(code)}</strong>?</p>`, footerHtml);
    }

    async function confirmDeletePlan(code) {
      await api(`/plans/${code}`, { method: 'DELETE' });
      showToast('Plan deleted.');
      closeModal();
      await refresh();
    }

    // Overview widgets. Small inline SVG icons follow the pill-icon pattern:
    // decorative (aria-hidden), currentColor, meaning always carried by text.
    const uiIcon = (body) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${body}</svg>`;
    // Shield: marks navigation that routes through the audited support-mode flow.
    const ICON_SHIELD = uiIcon('<path d="M12 3.8l6.8 2.5v5.1c0 4.2-2.9 7.4-6.8 8.8-3.9-1.4-6.8-4.6-6.8-8.8V6.3z"/><path d="M9.4 12l1.9 1.9 3.4-3.8"/>');

    function renderAcquisitionFunnel(usage) {
      const registrations30d = Number(usage.registrations_30d || 0);
      const converted30d = Number(usage.converted_registrations_30d || 0);
      const conversionRate = registrations30d ? Math.round((converted30d / registrations30d) * 100) : 0;
      const funnel = $('acquisitionFunnel');
      funnel.classList.remove('empty-state');
      funnel.replaceChildren();
      const wrap = document.createElement('div');
      wrap.className = 'funnel';
      const top = document.createElement('div');
      top.className = 'funnel-top';
      const registered = document.createElement('span');
      registered.className = 'tabular';
      registered.textContent = `${registrations30d} registrations`;
      const converted = document.createElement('span');
      converted.className = 'tabular';
      converted.textContent = `${converted30d} converted (${conversionRate}%)`;
      top.append(registered, converted);
      const bar = document.createElement('div');
      bar.className = 'funnel-bar';
      bar.setAttribute('aria-hidden', 'true'); // data lives in the text above
      const fill = document.createElement('div');
      fill.className = 'funnel-bar-fill';
      fill.style.width = `${Math.min(100, Math.max(0, conversionRate))}%`;
      bar.appendChild(fill);
      const sources = document.createElement('div');
      sources.className = 'funnel-sources';
      [
        ['', 'Studio Websites', Number(usage.portal_registrations_30d || 0)],
        ['accent', 'Quick Registration or campaigns', Number(usage.alternate_registrations_30d || 0)]
      ].forEach(([tone, label, count]) => {
        const row = document.createElement('div');
        row.className = 'funnel-source';
        const dot = document.createElement('span');
        dot.className = `funnel-dot ${tone}`.trim();
        dot.setAttribute('aria-hidden', 'true');
        const labelEl = document.createElement('span');
        labelEl.className = 'funnel-source-label';
        labelEl.textContent = label;
        const value = document.createElement('span');
        value.className = 'funnel-source-value tabular';
        value.textContent = count;
        row.append(dot, labelEl, value);
        sources.appendChild(row);
      });
      wrap.append(top, bar, sources);
      funnel.appendChild(wrap);
    }

    function renderPlansTable(errorMessage = '') {
      const plansBody = $('plansBody');
      if (!plansBody) return;
      plansBody.replaceChildren();
      if (errorMessage) {
        appendEmptyRow(plansBody, 5, errorMessage);
        return;
      }
      if (!plans.length) {
        appendEmptyRow(plansBody, 5, 'No plans configured.');
        return;
      }
      plans.forEach((p) => {
        const row = document.createElement('tr');
        row.dataset.planCode = String(p.code);
        row.classList.toggle('is-inspector-selected', inspectorMode === 'plan' && inspectorSelection === p.code);
        wireQuickViewRow(row, () => openPlanInspector(p), `View ${planDisplayName(p)}`);
        const nameCell = addCell(row);
        const strong = document.createElement('strong');
        const code = document.createElement('code');
        strong.textContent = planDisplayName(p);
        code.textContent = text(p.code);
        nameCell.append(strong, document.createElement('br'), code);
        addCell(row, money(p.monthly_price_aud));
        renderPlanQuota(addCell(row), p);
        const publication = addCell(row);
        const state = document.createElement('span');
        state.className = p.is_public ? 'pill active' : 'pill archived';
        state.textContent = p.is_public ? 'Published' : 'Not published';
        publication.appendChild(state);
        if (p.is_recommended) {
          const badge = document.createElement('span');
          badge.className = 'pill warning';
          badge.style.marginLeft = '6px';
          badge.textContent = 'Recommended';
          publication.appendChild(badge);
        }
        const actions = document.createElement('div');
        actions.className = 'action-row';
        addActionButton(actions, 'Actions', 'btn-secondary btn-sm', (button) => openPlanActions(p.code, button));
        addCell(row, '', 'Actions').appendChild(actions);
        plansBody.appendChild(row);
      });
      window.AdminI18n?.localise?.(plansBody);
    }

    // Audit log table. Rendered from cached rows so a language switch can
    // re-format the timestamps (the formatted value is locale-specific and is
    // not a dictionary string); the raw server timestamp stays in the title.
    function filteredAuditLogs() {
      const q = ($('auditSearch')?.value || '').trim().toLowerCase();
      if (!q) return auditLogs;
      return auditLogs.filter((a) =>
        `${a.action || ''} ${a.tenant_slug || ''} ${a.resource_type || ''} ${a.resource_id || ''}`
          .toLowerCase().includes(q));
    }

    function auditMetadata(value) {
      if (!value) return {};
      if (typeof value === 'object') return value;
      try { return JSON.parse(String(value)); }
      catch (_) { return { value: String(value) }; }
    }

    function buildAuditDetail(a) {
      const metadata = auditMetadata(a.metadata);
      const wrap = document.createElement('div');
      wrap.className = 'detail-grid';
      const field = (label, value) => {
        const item = document.createElement('div');
        item.className = 'detail-item';
        const labelEl = document.createElement('div');
        labelEl.className = 'detail-label';
        relabel(labelEl, label);
        const valueEl = document.createElement('div');
        valueEl.className = 'detail-value';
        valueEl.textContent = text(value);
        item.append(labelEl, valueEl);
        wrap.appendChild(item);
      };
      field('Time', formatTimestamp(a.created_at));
      field('Tenant', a.tenant_slug);
      field('Action', a.action);
      field('Resource type', a.resource_type);
      field('Resource ID', a.resource_id);
      field('Actor', a.actor_email || 'System');

      const support = metadata && typeof metadata.support_session === 'object'
        ? metadata.support_session : null;
      if (support?.reason) field('Support reason', support.reason);

      const metadataItem = document.createElement('div');
      metadataItem.className = 'detail-item';
      metadataItem.style.gridColumn = '1 / -1';
      const metadataLabel = document.createElement('div');
      metadataLabel.className = 'detail-label';
      relabel(metadataLabel, 'Metadata');
      const pre = document.createElement('pre');
      pre.className = 'audit-metadata';
      pre.textContent = Object.keys(metadata).length
        ? JSON.stringify(metadata, null, 2)
        : 'No metadata captured.';
      metadataItem.append(metadataLabel, pre);
      wrap.appendChild(metadataItem);
      return wrap;
    }

    function openAuditDetail(a) {
      openAuditInspector(a);
    }

    /* The endpoint returns 100 rows and this table used to render all of them:
       a hundred-row wall with a UUID in every fourth cell, no filter, and the
       one line an operator came to find somewhere inside it. Same page size and
       controls as the tenants table so the two behave alike. */
    function renderAuditLogs() {
      const auditBody = $('auditBody');
      auditBody.replaceChildren();
      const matches = filteredAuditLogs();
      const totalPages = Math.max(1, Math.ceil(matches.length / auditPageSize));
      if (auditPage >= totalPages) auditPage = totalPages - 1;
      if (auditPage < 0) auditPage = 0;
      relabel($('auditPageLabel'), `Page ${auditPage + 1} of ${totalPages}`);
      $('auditPrevBtn').disabled = auditPage <= 0;
      $('auditNextBtn').disabled = auditPage >= totalPages - 1;
      relabel($('auditCountLabel'), auditLogs.length ? `${matches.length} of ${auditLogs.length} events` : '');
      if (!matches.length) {
        appendEmptyRow(auditBody, 4, auditLogs.length ? 'No events match this filter.' : 'No audit logs yet.');
        return;
      }
      matches.slice(auditPage * auditPageSize, (auditPage + 1) * auditPageSize).forEach((a) => {
        const row = document.createElement('tr');
        const auditId = a.id || `${a.created_at}:${a.resource_id}`;
        row.dataset.auditId = String(auditId);
        row.classList.toggle('is-inspector-selected', inspectorMode === 'audit' && inspectorSelection === auditId);
        const timeCell = addCell(row, formatTimestamp(a.created_at));
        timeCell.className = 'tabular';
        if (a.created_at) timeCell.title = String(a.created_at);
        addCell(row, text(a.tenant_slug));
        addStrongMuted(addCell(row), a.action);
        /* The resource id is a UUID that made the column the widest on the page
           for a string nobody reads in full. Truncated in the cell, complete in
           the title and selectable by widening the column. */
        const resource = addCell(row, `${text(a.resource_type)} ${text(a.resource_id)}`);
        resource.className = 'audit-resource';
        resource.title = `${text(a.resource_type)} ${text(a.resource_id)}`;
        const detailButton = document.createElement('button');
        detailButton.type = 'button';
        detailButton.className = 'audit-resource-detail';
        detailButton.textContent = 'Details';
        detailButton.addEventListener('click', () => openAuditDetail(a));
        resource.appendChild(detailButton);
        auditBody.appendChild(row);
      });
    }

    document.addEventListener('studiosaas:admin-language', () => {
      updateWorkspaceHeaderOffset();
      renderWorkspaceContext();
      if (currentUser) {
        renderTenants();
        renderPlansTable();
        renderAuditLogs();
        rerenderInspector();
      }
    });

    // Main refresh function
    async function refresh() {
      if (!currentUser) return;
      workspaceFailures = [];
      workspaceLoadError = false;
      if ($('workspaceDataState')) renderWorkspaceContext();
      setLoading(true);
      try {
        const [usageResult, planResult, tenantResult, auditResult, settlementResult] =
          await Promise.allSettled([
            api('/admin/usage'), api('/plans'), api('/admin/tenants'), api('/admin/audit-logs'),
            api('/admin/subscriptions/settlement')
          ]);
        const failureMessage = (label, result) => {
          const detail = result.reason?.message || 'Request failed.';
          return `${label}: ${detail}`;
        };
        if (tenantResult.status !== 'fulfilled') {
          throw new Error(failureMessage('Tenants', tenantResult));
        }

        const partialFailures = [];
        tenants = tenantResult.value.tenants || [];
        if (planResult.status === 'fulfilled') {
          plans = planResult.value.plans || [];
        } else {
          plans = [];
          partialFailures.push(failureMessage('Plans', planResult));
        }
        fillPlanSelect();

        if (usageResult.status === 'fulfilled') {
          const usage = usageResult.value.usage;
          $('tenantCount').textContent = usage.tenants;
          $('mrrCount').textContent = money(usage.mrr_aud);
          $('paidTenantCount').textContent = usage.paid_tenants;
          $('trialTenantCount').textContent = usage.trial_tenants;
          $('onboardingTenantCount').textContent = usage.onboarding_tenants;
          $('pastDueTenantCount').textContent = usage.past_due_tenants;
          $('trialEndingCount').textContent = usage.trials_ending_7d;
          $('newTenantCount').textContent = usage.new_tenants_30d;
          renderAcquisitionFunnel(usage);
        } else {
          ['tenantCount', 'mrrCount', 'paidTenantCount', 'trialTenantCount',
           'onboardingTenantCount', 'pastDueTenantCount', 'trialEndingCount', 'newTenantCount']
            .forEach((id) => { $(id).textContent = 'Unavailable'; });
          $('acquisitionFunnel').textContent = failureMessage('Acquisition funnel', usageResult);
          $('acquisitionFunnel').classList.add('empty-state');
          partialFailures.push(failureMessage('Usage', usageResult));
        }

        renderPlansTable(
          planResult.status === 'fulfilled'
            ? ''
            : failureMessage('Plans unavailable', planResult),
        );

        renderAttentionQueue();
        renderTenants();

        if (settlementResult.status === 'fulfilled') {
          settlement = settlementResult.value;
          const total = Object.values(settlement.counts || {}).reduce((a, b) => a + b, 0);
          $('settlementCount').textContent = String(total);
        } else {
          settlement = null;
          $('settlementCount').textContent = 'Unavailable';
          partialFailures.push(failureMessage('Subscription dates', settlementResult));
        }

        if (auditResult.status === 'fulfilled') {
          auditLogs = auditResult.value.auditLogs || [];
          auditPage = 0;
          renderAuditLogs();
        } else {
          auditLogs = [];
          const auditBody = $('auditBody');
          auditBody.replaceChildren();
          $('auditCountLabel').textContent = '';
          appendEmptyRow(auditBody, 4, failureMessage('Audit logs unavailable', auditResult));
          partialFailures.push(failureMessage('Audit logs', auditResult));
        }
        if (partialFailures.length) {
          showToast(`Partial load — ${partialFailures.join(' · ')}`, 'error');
        }
        workspaceFailures = partialFailures;
        lastRefreshAt = new Date();
        workspaceLoadError = false;
        renderWorkspaceContext();

      } catch (err) {
        if (err.status === 401) {
          workspaceFailures = [];
          workspaceLoadError = false;
          lastRefreshAt = null;
          setAuthState(null);
          showToast('Please log in to continue.', 'error');
        } else {
          workspaceFailures = [err.message];
          workspaceLoadError = true;
          renderWorkspaceContext();
          showToast('Failed to load data: ' + err.message, 'error');
        }
      } finally {
        setLoading(false);
        if (currentUser) rerenderInspector();
      }
    }

    // Event listeners
    $('loginForm').addEventListener('submit', loginSuperAdmin);
    document.addEventListener('keydown', (event) => {
      if (event.key !== 'Escape') return;
      if (activeActionMenu) closeActionMenu();
      else if (mobileNavOpen) setMobileNavOpen(false);
      else if (isWorkspaceEditorOpen()) closeWorkspaceEditor();
      else if ($('modalOverlay').classList.contains('active')) closeModal();
    });
    $('logoutBtn').addEventListener('click', logoutSuperAdmin);
    $('changePasswordBtn').addEventListener('click', openChangePasswordModal);
    $('refreshBtn').addEventListener('click', refresh);
    /* The metric filter is NOT cleared here any more. It used to be, so typing
       one character into search silently dropped the filter the operator had
       just arrived with. Now it composes with the toolbar and is removed only
       by its own chip or by Clear Filters — which is the point of the chip. */
    ['tenantSearch','statusFilter','planFilter','categoryFilter','showTestTenants'].forEach((id) => $(id).addEventListener('input', () => {
      tenantPage = 0;
      renderTenants();
    }));
    document.querySelectorAll('.stats-grid button.stat-card[data-metric]').forEach((card) => {
      card.addEventListener('click', () => {
        // Clicking the pressed counter releases it, so the card is its own undo.
        setMetricFilter(card.dataset.metric === metricFilter ? '' : card.dataset.metric);
        history.pushState(null, '', '#tenants');
        setActiveWorkspace('tenants');
      });
    });
    $('metricFilterClear').addEventListener('click', () => setMetricFilter(''));
    navLinks = Array.from(document.querySelectorAll('[data-platform-rail][data-workspace-nav]'));
    setActiveNav = (hash) => {
      navLinks.forEach((link) => {
        const active = link.getAttribute('href') === hash;
        link.classList.toggle('active', active);
        if (active) link.setAttribute('aria-current', 'page');
        else link.removeAttribute('aria-current');
      });
    };
    navLinks.forEach((link) => link.addEventListener('click', (event) => {
      event.preventDefault();
      setMobileNavOpen(false);
      const hash = link.getAttribute('href') || '#overview';
      if (isWorkspaceEditorOpen() && !closeWorkspaceEditor()) return;
      history.pushState(null, '', hash);
      setActiveWorkspace(hash.replace(/^#/, ''));
    }));
    $('platformMobileNavToggle').addEventListener('click', () => setMobileNavOpen(!mobileNavOpen));
    $('platformMobileNavScrim').addEventListener('click', () => setMobileNavOpen(false));
    $('attentionShortcut').addEventListener('click', () => {
      setMobileNavOpen(false);
      history.pushState(null, '', '#overview');
      setActiveWorkspace('overview');
      requestAnimationFrame(() => $('attentionQueue')?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
    });
    $('workspaceInspectorClose').addEventListener('click', closeInspector);
    $('workspaceEditorClose').addEventListener('click', () => closeWorkspaceEditor());
    window.addEventListener('hashchange', () => setActiveWorkspace(workspaceFromHash()));
    window.addEventListener('resize', updateWorkspaceHeaderOffset, { passive: true });
    $('workspaceRetryBtn').addEventListener('click', refresh);
    updateWorkspaceHeaderOffset();
    setActiveWorkspace(workspaceFromHash(), { scroll: false });
    $('clearFiltersBtn').addEventListener('click', () => {
      $('tenantSearch').value = '';
      $('statusFilter').value = '';
      $('planFilter').value = '';
      $('categoryFilter').value = '';
      $('showTestTenants').checked = false;
      setMetricFilter('');
    });
    $('tenantPrevBtn').addEventListener('click', () => { tenantPage = Math.max(0, tenantPage - 1); renderTenants(); });
    $('tenantNextBtn').addEventListener('click', () => { tenantPage += 1; renderTenants(); });
    $('auditSearch').addEventListener('input', () => { auditPage = 0; renderAuditLogs(); });
    $('auditPrevBtn').addEventListener('click', () => { auditPage = Math.max(0, auditPage - 1); renderAuditLogs(); });
    $('auditNextBtn').addEventListener('click', () => { auditPage += 1; renderAuditLogs(); });

    // Add tenant button - open the center create workspace
    $('addTenantBtn').addEventListener('click', () => {
      editingTenantId = '';
	      const bodyHtml = `
	        <div class="form-grid">
	          <div class="form-group"><label for="m_tenantName">Studio Name</label><input id="m_tenantName" placeholder="Northside Art Studio" data-i18n-lock></div>
	          <div class="form-group"><label for="m_tenantSlug">Slug</label><input id="m_tenantSlug" readonly><small>Auto-generated from studio name.</small></div>
	          <div class="form-group"><label for="m_tenantPlan">Plan</label><select id="m_tenantPlan">${/*safe*/plans.map(p => `<option value="${esc(p.code)}">${esc(planDisplayName(p))}</option>`).join('')}</select></div>
	          <div class="form-group"><label for="m_tenantCategory">Studio Category</label><select id="m_tenantCategory">${/*safe*/categoryOptions('general')}</select></div>
	          <div class="form-group"><label for="m_ownerName">Owner Name</label><input id="m_ownerName" placeholder="Studio Owner"></div>
	          <div class="form-group"><label for="m_ownerEmail">Owner Email</label><input id="m_ownerEmail" type="email" placeholder="owner@studio.test"></div>
	          <div class="form-group" style="grid-column:span 2;"><label for="m_studioAdminPassword">Temporary Admin Password</label><input id="m_studioAdminPassword" type="password" minlength="8" autocomplete="new-password" required placeholder="At least 8 characters"><small>Required for initial access. Share it through a secure channel, then ask the owner to change it.</small></div>
	          <div class="form-group" style="grid-column:span 2;"><label for="m_tenantSlogan">Slogan</label><input id="m_tenantSlogan" value="${esc(presetSlogan('general'))}"></div>
	        </div>
          <div class="summary-item">
            <div class="summary-label">Auto-filled</div>
            <div class="summary-value">Contact email, billing email, Studio Admin login, onboarding status, and first 30-day trial period.</div>
          </div>
	      `;
      const footerHtml = `<span class="editor-footer-note">The first 30-day trial is generated on create.</span><button id="m_saveTenant" onclick="saveNewTenant()" class="btn-primary">Create Tenant</button><button onclick="closeWorkspaceEditor()" class="btn-secondary">Cancel</button>`;
      openWorkspaceEditor({
        workspace: 'tenants',
        kind: 'tenant',
        title: 'Add Tenant',
        subtitle: 'Create a studio workspace and prepare its first admin access.',
        bodyHtml,
        footerHtml
      });
        const syncSlug = () => { $('m_tenantSlug').value = slugifyTenantName($('m_tenantName').value); };
        $('m_tenantName').addEventListener('input', syncSlug);
	      $('m_tenantCategory').addEventListener('change', () => {
	        $('m_tenantSlogan').value = presetSlogan($('m_tenantCategory').value);
	      });
        syncSlug();
	    });

    async function saveNewTenant() {
      const ownerEmail = $('m_ownerEmail').value.trim();
      const payload = {
        name: $('m_tenantName').value,
        slug: $('m_tenantSlug').value || slugifyTenantName($('m_tenantName').value),
        status: 'onboarding',
        planCode: $('m_tenantPlan').value,
	        category: $('m_tenantCategory').value,
	        slogan: $('m_tenantSlogan').value,
        studioAdminEmail: ownerEmail,
        studioAdminName: $('m_ownerName').value,
        studioAdminPassword: $('m_studioAdminPassword').value,
        subscriptionStatus: 'trialing',
        startsAt: new Date().toISOString().slice(0, 10),
        endsAt: null,
        trialEndsAt: addDaysIso(30),
        currentPeriodEndsAt: addDaysIso(30),
        ownerName: $('m_ownerName').value,
        ownerRole: 'Owner',
        ownerPhone: '',
        ownerEmail,
        contactPhone: '',
        contactEmail: ownerEmail,
        billingEmail: ownerEmail,
        abn: '',
        website: '',
        address: '',
        notes: ''
      };

      if (!payload.name || !payload.slug || !payload.ownerEmail || !payload.ownerName || !payload.planCode || payload.studioAdminPassword.length < 8) {
        showToast('Studio name, owner details, plan, and an admin password of at least 8 characters are required.', 'error');
        return;
      }

      const saveButton = $('m_saveTenant');
      const finish = beginSaving(saveButton, 'Creating…');
      $('platformEditWorkspace')?.classList.add('is-submitting');
      setWorkspaceEditorState('Creating…', false);
      try {
        await api('/admin/tenants', { method: 'POST', body: JSON.stringify(payload) });
      } catch (error) {
        finish();
        $('platformEditWorkspace')?.classList.remove('is-submitting');
        setWorkspaceEditorState('Create failed', true);
        throw error;
      }
      finish();
      $('platformEditWorkspace')?.classList.remove('is-submitting');
      setWorkspaceEditorState('Created', false);
      showToast('Tenant created.');
      closeWorkspaceEditor({ confirm: false, focus: false });
      await refresh();
    }

		    $('addPlanBtn').addEventListener('click', resetPlanForm);

    // Close modal on overlay click
    $('modalOverlay').addEventListener('click', (e) => {
      if (e.target === $('modalOverlay')) closeModal();
    });
    $('modalOverlay').addEventListener('keydown', trapModalFocus);

    // Initial load
    setAuthState(null);
    loadIndustryPresets().then(checkSession);
