    /* eslint-disable no-empty */
    /* globals API_BASE, WORKFLOW_STEPS, STATUS_FILTERS, SEV_ICON, _RISK_MAP,
       _REC_MAP, _SEV_ORDER, activeStatusFilter, currentStats, allUsers,
       currentUsername, intakesById, _riskClass, _riskIcon, fmt, esc, initIcons,
       toast, renderWorkflowTrack, pickupReadyMessage, notifyPickupBrowser,
       copyPickupMessage, fallbackCopy, openPickupSms, openPickupEmail,
       digitsForWhatsApp, bindPickupNotifyDelegation, buildPatientContextString,
       _parsePatientContext, fetchWithTimeout, _tokenize, computeAllergyWarnings,
       computeLifestyleWarnings, parseCounselingPoints */
    /* ============ Rendering ============ */
    function renderInteractionsList(interactions = []) {
      if (!interactions.length) {
        return `<div class="empty-callout"><i data-lucide="check-circle-2"></i> No known drug-drug interactions found in current knowledge base.</div>`;
      }
      const sorted = [...interactions].sort((a, b) => {
        const ai = _SEV_ORDER.indexOf((a.severity || 'unknown').toLowerCase());
        const bi = _SEV_ORDER.indexOf((b.severity || 'unknown').toLowerCase());
        return ai - bi;
      });
      return sorted.map(i => {
        const sev = (i.severity || 'unknown').toLowerCase();
        const sevSafe = _SEV_ORDER.includes(sev) ? sev : 'unknown';
        const risk = i.riskFactor || _RISK_MAP[sevSafe] || 'Unknown';
        const rec = i.recommendation || _REC_MAP[sevSafe] || _REC_MAP.unknown;
        const exp = i.explanation || i.description || 'Interaction identified.';
        return `
          <div class="ix-card sev-${sevSafe}">
            <div class="ix-head">
              <span class="sev-tag sev-${sevSafe}"><i data-lucide="${SEV_ICON[sevSafe]}"></i>${esc(i.severity || 'Unknown')}</span>
              <span class="ix-pair">${esc(i.drug1 || '?')} <em>+</em> ${esc(i.drug2 || '?')}</span>
              <span class="risk-badge ${_riskClass(risk)}" style="margin-left:auto;"><i data-lucide="${_riskIcon(risk)}"></i>${esc(risk)}</span>
            </div>
            <div class="ix-explain">${esc(exp)}</div>
            <div class="ix-rec"><strong>Recommendation:</strong> ${esc(rec)}</div>
            ${i.monitoring ? `<div style="margin-top:6px;"><span class="pill"><i data-lucide="activity"></i> Monitor: ${esc(i.monitoring)}</span></div>` : ''}
            ${i.source ? `<div class="ix-source">Source: ${esc(i.source)}</div>` : ''}
          </div>`;
      }).join('');
    }

    function renderEvaluateResult(data) {
      if (!data.success) {
        return `<div class="error-state"><i data-lucide="alert-octagon"></i><div><strong>Analysis failed</strong><div>${esc(data.error || 'See intake card for interaction details.')}</div></div></div>`;
      }
      const interactions = data.interactions || [];
      const allergyWarnings = data.allergyWarnings || [];
      const lifestyleWarnings = data.lifestyleWarnings || [];
      const risk = data.overallRisk || 'Unknown';
      const rc = _riskClass(risk);
      const ri = _riskIcon(risk);

      let html = `
        <div class="row-between" style="margin-bottom:14px;">
          <span class="overline" style="font-family:var(--font-mono); font-size:0.7rem; text-transform:uppercase; letter-spacing:0.16em; color:var(--text-muted);">Overall risk</span>
          <span class="risk-badge ${rc}"><i data-lucide="${ri}"></i> ${esc(risk)}</span>
        </div>
        <div class="section-head"><i data-lucide="shield-alert"></i>Drug interactions <span class="count-pill">${interactions.length}</span></div>
        ${renderInteractionsList(interactions)}
      `;
      if (allergyWarnings.length) {
        html += `
          <div class="section-head" style="margin-top:14px;"><i data-lucide="ban"></i>Allergy warnings <span class="count-pill">${allergyWarnings.length}</span></div>
          <div class="warn-box allergy"><i data-lucide="ban"></i><ul>${allergyWarnings.map(w => `<li>${esc(w)}</li>`).join('')}</ul></div>
        `;
      }
      if (lifestyleWarnings.length) {
        html += `
          <div class="section-head" style="margin-top:14px;"><i data-lucide="heart-pulse"></i>Lifestyle cautions <span class="count-pill">${lifestyleWarnings.length}</span></div>
          <div class="warn-box lifestyle"><i data-lucide="heart-pulse"></i><ul>${lifestyleWarnings.map(w => `<li>${esc(w)}</li>`).join('')}</ul></div>
        `;
      }
      return html;
    }

    function getNextTransitions(status) {
      const map = {
        new: ['triage'],
        triage: ['waiting_info', 'ready_to_fill'],
        waiting_info: ['ready_to_fill'],
        ready_to_fill: ['filled'],
        filled: ['dispensed'],
        dispensed: ['completed'],
        completed: []
      };
      return map[status] || [];
    }

    function statusLabel(s) {
      return (STATUS_FILTERS.find(f => f.key === s) || {}).label || s.replace('_', ' ');
    }

    /* ============ Stats ============ */
    function renderStatsSkeleton() {
      const stats = document.getElementById('stats');
      const items = [0,1,2,3,4];
      stats.innerHTML = items.map(() => `
        <div class="stat skel">
          <div class="stat-icon"></div>
          <div class="stat-body">
            <span class="label label-skel">label</span>
            <span class="value">0</span>
          </div>
        </div>`).join('');
    }
    function renderStats(s) {
      currentStats = s;
      const stats = document.getElementById('stats');
      stats.innerHTML = `
        <div class="stat" data-testid="stat-total">
          <div class="stat-icon"><i data-lucide="layers"></i></div>
          <div class="stat-body"><span class="label">Total intakes</span><span class="value">${s.total || 0}</span></div>
        </div>
        <div class="stat neutral" data-testid="stat-new">
          <div class="stat-icon"><i data-lucide="inbox"></i></div>
          <div class="stat-body"><span class="label">New</span><span class="value">${s.by_status?.new || 0}</span></div>
        </div>
        <div class="stat warning" data-testid="stat-ready">
          <div class="stat-icon"><i data-lucide="list-checks"></i></div>
          <div class="stat-body"><span class="label">Ready to fill</span><span class="value">${s.by_status?.ready_to_fill || 0}</span></div>
        </div>
        <div class="stat success" data-testid="stat-pickup">
          <div class="stat-icon"><i data-lucide="package-check"></i></div>
          <div class="stat-body"><span class="label">Ready for pickup</span><span class="value">${s.ready_for_pickup ?? 0}</span></div>
        </div>
        <div class="stat purple" data-testid="stat-dispensed">
          <div class="stat-icon"><i data-lucide="check-circle-2"></i></div>
          <div class="stat-body"><span class="label">Dispensed</span><span class="value">${s.dispensed_count || 0}</span></div>
        </div>
      `;
      initIcons();
    }
    async function loadStatistics() {
      try {
        const res = await fetchWithTimeout(`${API_BASE}/intakes/stats/summary`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        renderStats(await res.json());
      } catch (e) {
        console.error('Stats error', e);
      }
    }

    /* ============ Filter chips ============ */
    function renderFilterBar() {
      const bar = document.getElementById('filter-bar');
      const inner = STATUS_FILTERS.map(f => {
        const count = !f.key
          ? (currentStats?.total ?? '')
          : (currentStats?.by_status?.[f.key] ?? '');
        const isActive = f.key === activeStatusFilter ? ' active' : '';
        return `
          <button type="button" class="chip${isActive}" data-status="${f.key}" data-testid="filter-chip-${f.key || 'all'}">
            ${esc(f.label)}
            ${count !== '' ? `<span class="count">${count}</span>` : ''}
          </button>
        `;
      }).join('');
      bar.innerHTML = `<span class="filter-label">Filter</span>${inner}`;
      bar.querySelectorAll('.chip').forEach(btn => {
        btn.addEventListener('click', () => {
          activeStatusFilter = btn.getAttribute('data-status') || '';
          renderFilterBar();
          loadIntakes();
        });
      });
    }

    /* ============ Audit trail ============ */
    async function loadAuditTrail(intakeId, container) {
      try {
        const res = await fetchWithTimeout(`${API_BASE}/intakes/${intakeId}/history`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const history = await res.json();
        if (!history.length) {
          container.innerHTML = `<div class="audit-head"><i data-lucide="history"></i>Audit trail</div><div style="font-size:0.82rem; color:var(--text-muted);">No transitions recorded yet.</div>`;
          initIcons();
          return;
        }
        const formatted = history.slice(-6).reverse().map(h => {
          const when = new Date(h.changed_at).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
          const by = h.changed_by ? ` by <span class="audit-by">@${esc(h.changed_by)}</span>` : '';
          const from = h.from_status ? `<strong>${esc(statusLabel(h.from_status))}</strong> → ` : '';
          return `<li><span class="audit-when">${esc(when)}</span><span class="audit-step">${from}<strong>${esc(statusLabel(h.to_status))}</strong>${by}</span></li>`;
        }).join('');
        const moreBtn = history.length > 6
          ? `<button type="button" class="btn ghost xs" style="margin-left:auto;" onclick="openAuditModal(${intakeId})" data-testid="view-full-audit-${intakeId}"><i data-lucide="list-tree"></i>View all ${history.length}</button>`
          : `<button type="button" class="btn ghost xs" style="margin-left:auto;" onclick="openAuditModal(${intakeId})" data-testid="view-full-audit-${intakeId}"><i data-lucide="list-tree"></i>Full history</button>`;
        container.innerHTML = `<div class="audit-head" style="display:flex; align-items:center; gap:8px;"><i data-lucide="history"></i>Audit trail <span class="count-pill">${history.length}</span>${moreBtn}</div><ol>${formatted}</ol>`;
        initIcons();
      } catch (e) {
        container.innerHTML = `<div class="audit-head"><i data-lucide="history"></i>Audit trail</div><div style="font-size:0.82rem; color:var(--text-muted);">Could not load history.</div>`;
        initIcons();
      }
    }

    /* Full audit-trail modal — timeline view for one intake. */
    async function openAuditModal(intakeId) {
      const modal    = document.getElementById('audit-modal');
      const body     = document.getElementById('audit-modal-body');
      const subtitle = document.getElementById('audit-modal-subtitle');
      const title    = document.getElementById('audit-modal-title');
      if (!modal || !body) return;

      const intake = intakesById.get(intakeId);
      title.textContent = `Full audit trail — Order #${intakeId}`;
      subtitle.textContent = intake && intake.patient_name
        ? `Patient: ${intake.patient_name} · complete transition history.`
        : 'Complete transition history for this intake.';
      body.innerHTML = `<div class="skel-line w-80"></div><div class="skel-line w-60"></div><div class="skel-line w-50"></div>`;
      modal.classList.add('open');

      try {
        const res = await fetchWithTimeout(`${API_BASE}/intakes/${intakeId}/history`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const history = await res.json();
        if (!history.length) {
          body.innerHTML = `<div style="padding:12px; color:var(--text-muted); text-align:center;">No transitions recorded for this intake yet.</div>`;
          return;
        }
        // Full timeline, newest first
        const rows = [...history].reverse().map((h, idx) => {
          const when = new Date(h.changed_at).toLocaleString(undefined, {
            year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
          });
          const from = h.from_status ? esc(statusLabel(h.from_status)) : '<em style="color:var(--text-muted);">start</em>';
          const to   = esc(statusLabel(h.to_status));
          const by   = h.changed_by
            ? `<span class="audit-by">@${esc(h.changed_by)}</span>`
            : `<span style="color:var(--text-muted); font-style:italic;">unknown</span>`;
          return `
            <li class="audit-timeline-row" data-testid="audit-row-${intakeId}-${idx}">
              <div class="audit-timeline-dot"></div>
              <div class="audit-timeline-content">
                <div class="audit-timeline-when">${esc(when)}</div>
                <div class="audit-timeline-step"><strong>${from}</strong> → <strong>${to}</strong></div>
                <div class="audit-timeline-actor">by ${by}</div>
              </div>
            </li>`;
        }).join('');
        body.innerHTML = `<ol class="audit-timeline">${rows}</ol>`;
        initIcons();
      } catch (e) {
        body.innerHTML = `<div style="padding:12px; color:var(--danger-text, #b91c1c); text-align:center;">Could not load history: ${esc(e.message)}</div>`;
      }
    }

    function closeAuditModal() {
      const modal = document.getElementById('audit-modal');
      if (modal) modal.classList.remove('open');
    }

    /* ============ Concurrency viewers ============ */
    async function pollViewers() {
      const visible = Array.from(document.querySelectorAll('[data-intake-id]'))
        .map(el => parseInt(el.getAttribute('data-intake-id'), 10))
        .filter(n => Number.isFinite(n));
      if (!visible.length) return;
      try {
        const res = await fetchWithTimeout(`${API_BASE}/intakes/viewing`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ intake_ids: visible }),
        }, 6000);
        if (!res.ok) return;
        const data = await res.json();
        renderViewersForCards(data.viewers || {});
      } catch (_) { /* silent — non-critical */ }
    }
    function renderViewersForCards(viewersMap) {
      for (const [idStr, users] of Object.entries(viewersMap)) {
        const el = document.getElementById(`viewers-${idStr}`);
        if (!el) continue;
        if (!users || !users.length) {
          el.innerHTML = '';
          el.hidden = true;
          continue;
        }
        const chips = users.slice(0, 4).map(u =>
          `<span class="viewer-chip"><span class="viewer-dot"></span>@${esc(u)}</span>`
        ).join('');
        const extra = users.length > 4 ? ` <span>+${users.length - 4} more</span>` : '';
        el.innerHTML = `<i data-lucide="eye" style="width:14px;height:14px;"></i>
          <span>Also viewing:</span>${chips}${extra}`;
        el.hidden = false;
      }
      initIcons();
    }

    /* ============ Intake card ============ */
    function highestSevIdxFromInteractions(interactions) {
      return interactions.reduce((acc, i) => {
        const idx = _SEV_ORDER.indexOf((i.severity || 'unknown').toLowerCase());
        return idx < acc ? idx : acc;
      }, 99);
    }
    function overallRiskFromInteractions(interactions) {
      const idx = highestSevIdxFromInteractions(interactions);
      return idx <= 0 ? 'Very High'
           : idx === 1 ? 'High'
           : idx === 2 ? 'Moderate'
           : idx === 3 ? 'Low'
           : interactions.length ? 'Low'
           : 'None';
    }

    function buildIntakeCardHTML(intake) {
      let interactions = [];
      if (intake.drug_interactions) {
        try {
          interactions = typeof intake.drug_interactions === 'string'
            ? JSON.parse(intake.drug_interactions)
            : (Array.isArray(intake.drug_interactions) ? intake.drug_interactions : []);
        } catch (e) {}
      }
      // Re-sort defensively
      interactions.sort((a, b) => {
        const ai = _SEV_ORDER.indexOf((a.severity || 'unknown').toLowerCase());
        const bi = _SEV_ORDER.indexOf((b.severity || 'unknown').toLowerCase());
        return ai - bi;
      });

      const counselingPoints = parseCounselingPoints(intake.counseling_points || '');
      const ctx = _parsePatientContext(intake.notes);
      const allergyWarnings = computeAllergyWarnings(intake.patient_allergies, intake.medications, intake.current_medications);
      const lifestyleWarnings = computeLifestyleWarnings(ctx, intake.medications, intake.current_medications);
      const overallRisk = overallRiskFromInteractions(interactions);
      const rc = _riskClass(overallRisk);
      const ri = _riskIcon(overallRisk);

      const stageDisplay = esc((intake.stage_display || intake.status || '').replace('_', ' '));

      const waNum = digitsForWhatsApp(intake.patient_phone || '');
      const waMsgText = pickupReadyMessage(intake.id, intake.patient_name || '');
      const waUrl = waNum.length >= 10 ? `https://wa.me/${waNum}?text=${encodeURIComponent(waMsgText)}` : '';

      return `
        <article class="intake-card" data-intake-id="${intake.id}" data-testid="intake-card-${intake.id}">
          <div class="row-between">
            <div class="id-block">
              <span class="id-line">Order · #${intake.id}</span>
              <span class="name" data-testid="intake-name-${intake.id}">${esc(intake.patient_name || '—')}</span>
              <span class="meta">Created ${new Date(intake.created_at).toLocaleString(undefined, { month:'short', day:'numeric', year:'numeric', hour:'2-digit', minute:'2-digit' })}</span>
            </div>
            <div style="display:flex; gap:6px; align-items:center; flex-wrap:wrap;">
              <span class="risk-badge ${rc}" data-testid="risk-badge-${intake.id}"><i data-lucide="${ri}"></i> Risk: ${esc(overallRisk)}</span>
              <span class="badge status" data-testid="status-badge-${intake.id}"><i data-lucide="circle-dot"></i>${stageDisplay}</span>
              ${intake.assigned_to ? `<span class="pill" title="Assigned to"><i data-lucide="user-round"></i>${esc(intake.assigned_to)}</span>` : ''}
            </div>
          </div>

          <div class="stepper">${renderWorkflowTrack(intake.status)}</div>
          ${intake.workflow_hint ? `<div class="workflow-hint"><i data-lucide="arrow-right-circle"></i>${esc(intake.workflow_hint)}</div>` : ''}

          ${intake.pickup_ready ? `
            <div class="pickup-callout">
              <div class="pickup-head"><i data-lucide="package-check"></i>Ready for patient pickup</div>
              <div class="pickup-msg">Notify the patient that their prescription is ready. WhatsApp opens with the message prefilled (you tap Send — no API cost). Or use desktop alert, copy, SMS, or email.</div>
              <div class="pickup-actions">
                ${waUrl
                  ? `<a class="btn sm" href="${esc(waUrl)}" target="_blank" rel="noopener noreferrer" data-testid="pickup-whatsapp-${intake.id}"><i data-lucide="smartphone"></i>WhatsApp</a>`
                  : `<button type="button" class="btn sm" disabled title="Add a patient mobile number (10+ digits) for WhatsApp" data-testid="pickup-whatsapp-${intake.id}"><i data-lucide="smartphone"></i>WhatsApp</button>`
                }
                <button type="button" class="btn sm" data-pickup-action="browser" data-intake-id="${intake.id}" data-patient-name="${esc(intake.patient_name || '')}" data-testid="pickup-desktop-${intake.id}"><i data-lucide="bell-ring"></i>Desktop alert</button>
                <button type="button" class="btn sm" data-pickup-action="copy" data-intake-id="${intake.id}" data-patient-name="${esc(intake.patient_name || '')}" data-testid="pickup-copy-${intake.id}"><i data-lucide="clipboard-copy"></i>Copy</button>
                <button type="button" class="btn sm" data-pickup-action="sms" data-intake-id="${intake.id}" data-patient-name="${esc(intake.patient_name || '')}" data-testid="pickup-sms-${intake.id}"><i data-lucide="message-square"></i>SMS</button>
                <button type="button" class="btn sm" data-pickup-action="email" data-intake-id="${intake.id}" data-patient-name="${esc(intake.patient_name || '')}" data-testid="pickup-email-${intake.id}"><i data-lucide="mail"></i>Email</button>
              </div>
            </div>` : ''}

          <dl class="data-row">
            <dt>Patient</dt>
            <dd>Age ${esc(fmt(intake.patient_age))}${intake.patient_gender ? ` · ${esc(intake.patient_gender.charAt(0).toUpperCase() + intake.patient_gender.slice(1))}` : ''}${intake.patient_phone ? ` · ${esc(intake.patient_phone)}` : ''} · Allergies: ${esc(fmt(intake.patient_allergies))}</dd>
            <dt>Assigned</dt>
            <dd class="${intake.assigned_to ? '' : 'muted'}">${intake.assigned_to ? esc(intake.assigned_to) : 'Unassigned'}</dd>
            <dt>New meds</dt>
            <dd>${esc(fmt(intake.medications))}</dd>
            <dt>Current</dt>
            <dd>${esc(fmt(intake.current_medications))}</dd>
          </dl>

          <div class="ix-section">
            <div class="section-head"><i data-lucide="shield-alert"></i>Drug interactions <span class="count-pill">${interactions.length}</span></div>
            ${renderInteractionsList(interactions)}
          </div>

          ${allergyWarnings.length ? `
          <div class="ix-section">
            <div class="section-head"><i data-lucide="ban"></i>Allergy warnings <span class="count-pill">${allergyWarnings.length}</span></div>
            <div class="warn-box allergy"><i data-lucide="ban"></i><ul>${allergyWarnings.map(w => `<li>${esc(w)}</li>`).join('')}</ul></div>
          </div>` : ''}

          ${lifestyleWarnings.length ? `
          <div class="ix-section">
            <div class="section-head"><i data-lucide="heart-pulse"></i>Lifestyle cautions <span class="count-pill">${lifestyleWarnings.length}</span></div>
            <div class="warn-box lifestyle"><i data-lucide="heart-pulse"></i><ul>${lifestyleWarnings.map(w => `<li>${esc(w)}</li>`).join('')}</ul></div>
          </div>` : ''}

          <div class="ix-section">
            <div class="row-between" style="margin-bottom:4px;">
              <div class="section-head" style="margin-bottom:0;"><i data-lucide="message-circle"></i>Counseling points <span class="count-pill">${counselingPoints.length}</span></div>
              <button type="button" class="btn ghost xs" onclick="openCounselingEditor(${intake.id})" data-testid="edit-counseling-${intake.id}"><i data-lucide="pencil"></i>Edit</button>
            </div>
            ${counselingPoints.length
              ? `<ul class="counseling-list">${counselingPoints.map(p => `<li>${esc(p)}</li>`).join('')}</ul>`
              : `<div style="font-size:0.86rem; color:var(--text-muted);">No structured counseling points extracted.</div>`}
          </div>

          <div class="audit-trail" id="audit-${intake.id}" data-testid="audit-${intake.id}">
            <div class="audit-head"><i data-lucide="history"></i>Audit trail</div>
            <div class="skel-line w-80"></div>
            <div class="skel-line w-50"></div>
          </div>

          <div class="viewers-strip" id="viewers-${intake.id}" data-testid="viewers-${intake.id}" hidden></div>

          <div class="actions">
            ${buildActionButtons(intake)}
          </div>
        </article>
      `;
    }

    function buildActionButtons(intake) {
      // Check if current user can modify this intake
      const canModify = !intake.assigned_to || intake.assigned_to === currentUsername || !currentUsername;
      
      let html = '';
      
      // Status advancement buttons - only show if user has permission
      if (canModify) {
        html += getNextTransitions(intake.status).map(next => 
          `<button class="btn primary sm" onclick="updateStatus(${intake.id}, '${next}')" data-testid="advance-${intake.id}-${next}">
            <i data-lucide="arrow-right"></i>Move to ${esc(next.replace('_', ' '))}
          </button>`
        ).join('');
        
        // Dispense button
        if (intake.status === 'filled') {
          html += `<button class="btn success sm" onclick="dispenseMedication(${intake.id})" data-testid="dispense-${intake.id}">
            <i data-lucide="check"></i>Dispense
          </button>`;
        }
      } else {
        // Show disabled message if can't modify
        html += `<div style="padding:8px 12px; background:var(--warning-bg); border:1px solid var(--warning-border); border-radius:6px; font-size:0.82rem; color:var(--warning-text);">
          <i data-lucide="lock"></i> Assigned to ${esc(intake.assigned_to)} — only they can advance this prescription
        </div>`;
      }
      
      // Assignment and re-check buttons - always available
      html += `<button class="btn sm" onclick="assignIntake(${intake.id})" data-testid="assign-${intake.id}">
        <i data-lucide="user-plus"></i>${intake.assigned_to ? 'Reassign' : 'Assign'}
      </button>`;
      
      html += `<button class="btn warning sm" onclick="recheckInteractions(${intake.id})" data-testid="recheck-${intake.id}">
        <i data-lucide="refresh-cw"></i>Re-check
      </button>`;

      html += `<button class="btn ghost sm" onclick="exportIntakePdf(${intake.id})" data-testid="export-pdf-${intake.id}">
        <i data-lucide="file-down"></i>Export PDF
      </button>`;

      return html;
    }

    /* ============ PDF export (client-side, jsPDF, landscape 1-pager) ============ */
    async function exportIntakePdf(intakeId) {
      const intake = intakesById.get(intakeId);
      if (!intake) {
        toast({ title: 'Cannot export', message: 'Intake not loaded yet — refresh and try again.', type: 'error' });
        return;
      }
      if (!window.jspdf || !window.jspdf.jsPDF) {
        toast({ title: 'PDF library not ready', message: 'Try again in a moment.', type: 'error' });
        return;
      }

      // Fetch audit trail so the PDF shows the actual transitions history.
      let history = [];
      try {
        const res = await fetchWithTimeout(`${API_BASE}/intakes/${intakeId}/history`);
        if (res.ok) history = await res.json();
      } catch (_) { /* non-fatal — PDF still renders */ }

      let interactions = [];
      if (intake.drug_interactions) {
        try {
          interactions = typeof intake.drug_interactions === 'string'
            ? JSON.parse(intake.drug_interactions)
            : (Array.isArray(intake.drug_interactions) ? intake.drug_interactions : []);
        } catch (_) {}
      }
      interactions.sort((a, b) => _SEV_ORDER.indexOf((a.severity || 'unknown').toLowerCase())
                                - _SEV_ORDER.indexOf((b.severity || 'unknown').toLowerCase()));

      const ctx = _parsePatientContext(intake.notes);
      const allergyWarnings  = computeAllergyWarnings(intake.patient_allergies, intake.medications, intake.current_medications);
      const lifestyleWarnings = computeLifestyleWarnings(ctx, intake.medications, intake.current_medications);
      const counselingPoints = parseCounselingPoints(intake.counseling_points || '');
      const overallRisk = overallRiskFromInteractions(interactions);

      const { jsPDF } = window.jspdf;
      const doc = new jsPDF({ orientation: 'landscape', unit: 'pt', format: 'letter' });
      const W = doc.internal.pageSize.getWidth();
      const H = doc.internal.pageSize.getHeight();
      const M = 32; // margin
      const COL_GAP = 18;
      const COL_W = (W - M * 2 - COL_GAP) / 2;

      const dark = [24, 30, 44];
      const muted = [102, 112, 133];
      const rule = [220, 226, 238];
      const risk = {
        'Very High': [153, 27, 27],
        'High':      [180, 83, 9],
        'Moderate':  [161, 98, 7],
        'Low':       [21, 128, 61],
        'None':      [21, 128, 61],
        'Unknown':   [71, 85, 105],
      }[overallRisk] || [71, 85, 105];

      // ─── Header ───────────────────────────────────────────────────
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(20);
      doc.setTextColor(...dark);
      doc.text('RxFlow', M, 44);
      doc.setFont('helvetica', 'normal');
      doc.setFontSize(10);
      doc.setTextColor(...muted);
      doc.text('Pharmacist Summary — 1-Page Handoff', M, 60);

      // Right-side status pill
      const statusLbl = (intake.stage_display || intake.status || '—').replace(/_/g, ' ');
      const rightX = W - M;
      doc.setFontSize(11);
      doc.setFont('helvetica', 'bold');
      doc.setTextColor(...dark);
      doc.text(`Order #${intake.id}`, rightX, 44, { align: 'right' });
      doc.setFont('helvetica', 'normal');
      doc.setFontSize(9);
      doc.setTextColor(...muted);
      const createdStr = intake.created_at ? new Date(intake.created_at).toLocaleString() : '—';
      doc.text(`Created ${createdStr}`, rightX, 58, { align: 'right' });
      doc.text(`Status: ${statusLbl}   ·   Assigned: ${intake.assigned_to || 'Unassigned'}`,
               rightX, 72, { align: 'right' });

      // Risk banner
      doc.setFillColor(...risk);
      doc.roundedRect(M, 82, W - M * 2, 26, 4, 4, 'F');
      doc.setTextColor(255, 255, 255);
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(12);
      doc.text(`Overall interaction risk: ${overallRisk}`, M + 12, 100);
      doc.setFont('helvetica', 'normal');
      doc.setFontSize(10);
      doc.text(`${interactions.length} interaction${interactions.length === 1 ? '' : 's'}   ·   `
             + `${allergyWarnings.length} allergy warning${allergyWarnings.length === 1 ? '' : 's'}   ·   `
             + `${lifestyleWarnings.length} lifestyle caution${lifestyleWarnings.length === 1 ? '' : 's'}`,
             W - M - 12, 100, { align: 'right' });

      // Body: two columns starting at y=126
      let yL = 126, yR = 126;

      /* Helper: section header */
      const sectionHead = (label, x, y) => {
        doc.setDrawColor(...rule);
        doc.setLineWidth(0.5);
        doc.line(x, y + 3, x + COL_W, y + 3);
        doc.setFont('helvetica', 'bold');
        doc.setFontSize(10);
        doc.setTextColor(...dark);
        doc.text(label.toUpperCase(), x, y);
        return y + 16;
      };

      /* Helper: labelled row */
      const labelRow = (label, value, x, y, colW) => {
        doc.setFont('helvetica', 'bold');
        doc.setFontSize(9);
        doc.setTextColor(...muted);
        doc.text(label.toUpperCase(), x, y);
        doc.setFont('helvetica', 'normal');
        doc.setFontSize(10);
        doc.setTextColor(...dark);
        const lines = doc.splitTextToSize(String(value || '—'), colW - 60);
        doc.text(lines, x + 60, y);
        return y + Math.max(14, lines.length * 12);
      };

      /* Helper: bullet list */
      const bulletList = (items, x, y, colW, opts = {}) => {
        if (!items || !items.length) {
          doc.setFont('helvetica', 'italic');
          doc.setFontSize(9);
          doc.setTextColor(...muted);
          doc.text(opts.empty || 'None recorded.', x, y);
          return y + 12;
        }
        doc.setFont('helvetica', 'normal');
        doc.setFontSize(9.5);
        doc.setTextColor(...dark);
        for (const item of items) {
          const lines = doc.splitTextToSize(`• ${item}`, colW - 8);
          doc.text(lines, x, y);
          y += lines.length * 11.5;
          if (y > H - M - 20) return y; // page overflow guard (single-page target)
        }
        return y + 4;
      };

      // ─── Left column ─────────────────────────────────────────────
      yL = sectionHead('Patient', M, yL);
      yL = labelRow('Name',      intake.patient_name || '—', M, yL, COL_W);
      const age = intake.patient_age != null && intake.patient_age !== '' ? intake.patient_age : '—';
      const gender = intake.patient_gender
        ? intake.patient_gender.charAt(0).toUpperCase() + intake.patient_gender.slice(1)
        : '—';
      yL = labelRow('Age / Sex', `${age} · ${gender}`, M, yL, COL_W);
      yL = labelRow('Phone',     intake.patient_phone || '—', M, yL, COL_W);
      yL = labelRow('Allergies', intake.patient_allergies || 'NKDA', M, yL, COL_W);
      yL += 6;

      yL = sectionHead('Medications', M, yL);
      yL = labelRow('New',     intake.medications || '—',         M, yL, COL_W);
      yL = labelRow('Current', intake.current_medications || '—', M, yL, COL_W);
      yL += 6;

      yL = sectionHead('Pharmacist notes', M, yL);
      doc.setFont('helvetica', 'normal');
      doc.setFontSize(9.5);
      doc.setTextColor(...dark);
      {
        const notes = (intake.pharmacist_notes || intake.notes || '').replace(/\[Patient Context\][\s\S]*$/, '').trim();
        const lines = doc.splitTextToSize(notes || 'No pharmacist notes.', COL_W);
        doc.text(lines, M, yL);
        yL += Math.min(lines.length, 6) * 11.5 + 6;
      }

      // ─── Right column ────────────────────────────────────────────
      const RX = M + COL_W + COL_GAP;
      yR = sectionHead(`Drug interactions (${interactions.length})`, RX, yR);
      if (!interactions.length) {
        doc.setFont('helvetica', 'italic');
        doc.setFontSize(9);
        doc.setTextColor(...muted);
        doc.text('No interactions detected.', RX, yR);
        yR += 14;
      } else {
        doc.setFontSize(9.5);
        for (const ix of interactions.slice(0, 8)) {
          const sev = (ix.severity || 'unknown').toUpperCase();
          const pair = `${ix.drug_a || ix.a || '?'} + ${ix.drug_b || ix.b || '?'}`;
          doc.setFont('helvetica', 'bold');
          doc.setTextColor(...dark);
          doc.text(`[${sev}] ${pair}`, RX, yR);
          yR += 12;
          const desc = ix.description || ix.effect || '';
          if (desc) {
            doc.setFont('helvetica', 'normal');
            doc.setTextColor(...muted);
            const lines = doc.splitTextToSize(desc, COL_W - 8);
            doc.text(lines.slice(0, 2), RX + 6, yR);
            yR += Math.min(lines.length, 2) * 11 + 3;
          }
          if (yR > H - M - 90) break;
        }
        if (interactions.length > 8) {
          doc.setFont('helvetica', 'italic');
          doc.setFontSize(8.5);
          doc.setTextColor(...muted);
          doc.text(`… +${interactions.length - 8} more (see full record)`, RX, yR);
          yR += 12;
        }
      }
      yR += 4;

      if (allergyWarnings.length) {
        yR = sectionHead(`Allergy warnings (${allergyWarnings.length})`, RX, yR);
        yR = bulletList(allergyWarnings, RX, yR, COL_W);
        yR += 2;
      }
      if (lifestyleWarnings.length) {
        yR = sectionHead(`Lifestyle cautions (${lifestyleWarnings.length})`, RX, yR);
        yR = bulletList(lifestyleWarnings, RX, yR, COL_W);
        yR += 2;
      }

      yR = sectionHead(`Counseling points (${counselingPoints.length})`, RX, yR);
      yR = bulletList(counselingPoints, RX, yR, COL_W, { empty: 'No structured counseling points.' });

      // ─── Footer: audit trail (last 4) ─────────────────────────────
      const FY = H - M - 44;
      doc.setDrawColor(...rule);
      doc.setLineWidth(0.5);
      doc.line(M, FY - 6, W - M, FY - 6);
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(9);
      doc.setTextColor(...muted);
      doc.text('AUDIT TRAIL (most recent)', M, FY);
      doc.setFont('helvetica', 'normal');
      doc.setFontSize(9);
      doc.setTextColor(...dark);
      const recent = (history || []).slice(-4);
      if (!recent.length) {
        doc.setFont('helvetica', 'italic');
        doc.setTextColor(...muted);
        doc.text('No transitions recorded.', M, FY + 14);
      } else {
        recent.forEach((h, i) => {
          const when = h.changed_at ? new Date(h.changed_at).toLocaleString() : '';
          const from = (h.from_status || '—').replace(/_/g, ' ');
          const to   = (h.to_status   || '—').replace(/_/g, ' ');
          const by   = h.changed_by ? ` · by ${h.changed_by}` : '';
          doc.text(`${when}   ${from} → ${to}${by}`, M, FY + 14 + i * 11);
        });
      }

      // Bottom-right: generation stamp
      doc.setFont('helvetica', 'italic');
      doc.setFontSize(8);
      doc.setTextColor(...muted);
      doc.text(
        `Generated by ${currentUsername || 'pharmacist'} · ${new Date().toLocaleString()}`,
        W - M, H - M / 2,
        { align: 'right' }
      );

      const safeName = (intake.patient_name || 'patient').replace(/[^a-z0-9]+/gi, '_').toLowerCase();
      doc.save(`rxflow-intake-${intake.id}-${safeName}.pdf`);
      toast({ title: 'PDF exported', message: `Saved rxflow-intake-${intake.id}.pdf`, type: 'success' });
    }

    function renderIntakeListSkeleton(container) {
      const skel = `
        <div class="skel-card">
          <div class="skel-line w-30 tall"></div>
          <div class="skel-line w-100"></div>
          <div class="skel-line w-80"></div>
          <div class="skel-line w-50"></div>
        </div>`;
      container.innerHTML = skel + skel;
    }

    function renderEmptyState(container, opts = {}) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon"><i data-lucide="${opts.icon || 'inbox'}"></i></div>
          <h3>${esc(opts.title || 'No intakes yet')}</h3>
          <p>${esc(opts.message || 'Create a new intake from the form on the left to begin.')}</p>
        </div>`;
      initIcons();
    }

    function renderErrorState(container, message) {
      container.innerHTML = `
        <div class="error-state">
          <i data-lucide="alert-octagon"></i>
          <div><strong>Could not load data</strong><div>${esc(message || 'Please retry shortly.')}</div></div>
        </div>`;
      initIcons();
    }

    async function loadIntakes() {
      const list = document.getElementById('intake-list');
      renderIntakeListSkeleton(list);
      const url = activeStatusFilter
        ? `${API_BASE}/intakes?status=${activeStatusFilter}`
        : `${API_BASE}/intakes`;
      try {
        const res = await fetchWithTimeout(url);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const intakes = await res.json();
        if (!intakes.length) {
          renderEmptyState(list, {
            icon: 'inbox',
            title: activeStatusFilter ? 'No intakes match this filter' : 'No intakes yet',
            message: activeStatusFilter
              ? 'Try a different status, or clear the filter to see all intakes.'
              : 'Create a new intake from the form on the left to begin.',
          });
          return;
        }
        list.innerHTML = intakes.map(buildIntakeCardHTML).join('');
        intakes.forEach(i => intakesById.set(i.id, i));
        initIcons();
        intakes.forEach(i => {
          const el = document.getElementById(`audit-${i.id}`);
          if (el) loadAuditTrail(i.id, el);
        });
      } catch (e) {
        renderErrorState(list, e.message);
      }
    }

    /* ============ Patient search ============ */
    let patientSearchDebounce = null;
    async function runPatientSearch() {
      const input = document.getElementById('patient-search-input');
      const section = document.getElementById('patient-search-results-section');
      const out = document.getElementById('patient-search-results');
      const mainList = document.getElementById('intake-list');
      const filterBar = document.getElementById('filter-bar');
      if (!input || !out) return;
      const q = input.value.trim();
      if (!q) {
        section.style.display = 'none';
        out.innerHTML = '';
        // Restore main list visibility
        if (mainList) mainList.style.display = '';
        if (filterBar) filterBar.style.display = '';
        return;
      }
      // Hide main list & filter chips while searching (de-duplication)
      if (mainList) mainList.style.display = 'none';
      if (filterBar) filterBar.style.display = 'none';
      section.style.display = '';
      renderIntakeListSkeleton(out);
      try {
        const url = `${API_BASE}/intakes?search=${encodeURIComponent(q)}&limit=50`;
        const res = await fetchWithTimeout(url);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const intakes = await res.json();
        if (!intakes.length) {
          renderEmptyState(out, {
            icon: 'search-x',
            title: 'No matching intakes',
            message: `No intakes match "${q}". Try a different spelling.`,
          });
          return;
        }
        out.innerHTML = intakes.map(buildIntakeCardHTML).join('');
        intakes.forEach(i => intakesById.set(i.id, i));
        initIcons();
        intakes.forEach(i => {
          const el = document.getElementById(`audit-${i.id}`);
          if (el) loadAuditTrail(i.id, el);
        });
      } catch (e) {
        renderErrorState(out, e.message);
      }
    }
    function schedulePatientSearch() {
      clearTimeout(patientSearchDebounce);
      patientSearchDebounce = setTimeout(runPatientSearch, 350);
    }
    function refreshPatientSearchIfActive() {
      const el = document.getElementById('patient-search-input');
      if (el && el.value.trim()) runPatientSearch();
    }

    /* ============ Actions ============ */
    async function updateStatus(intakeId, status) {
      // Optimistic UI update - show loading state
      const card = document.querySelector(`[data-intake-id="${intakeId}"]`);
      if (card) {
        const actions = card.querySelector('.actions');
        if (actions) {
          const originalHTML = actions.innerHTML;
          actions.innerHTML = '<div style="display:flex;align-items:center;gap:8px;color:var(--text-muted);"><i data-lucide="loader-2" style="animation:spin 1s linear infinite;"></i>Updating...</div>';
          initIcons();
          
          // Add CSS for spin animation if not exists
          if (!document.getElementById('spin-animation')) {
            const style = document.createElement('style');
            style.id = 'spin-animation';
            style.textContent = '@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }';
            document.head.appendChild(style);
          }
        }
      }
      
      try {
        const res = await fetchWithTimeout(`${API_BASE}/intakes/${intakeId}/status`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ status })
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          toast({ title: 'Could not update status', message: err.detail || `HTTP ${res.status}`, type: 'error' });
          // Restore original state on error
          await loadIntakes();
          return;
        }
        toast({ title: 'Status updated', message: `Moved to ${statusLabel(status)}.`, type: 'success' });
        await loadIntakes();
        await loadStatistics();
        renderFilterBar();
        refreshPatientSearchIfActive();
      } catch (e) {
        toast({ title: 'Network error', message: e.message, type: 'error' });
        // Restore on error
        await loadIntakes();
      }
    }
    async function assignIntake(intakeId) {
      // Load all users if not already loaded
      if (!allUsers.length) {
        try {
          const res = await fetchWithTimeout(`${API_BASE}/api/auth/users`);
          if (res.ok) {
            const data = await res.json();
            allUsers = data.users || [];
          }
        } catch (e) {
          console.error('Failed to load users', e);
        }
      }

      // If we have users, show a select dialog, otherwise fallback to prompt
      if (allUsers.length > 0) {
        const options = allUsers.map(u => `<option value="${esc(u.username)}">${esc(u.username)} (${esc(u.email)})</option>`).join('');
        const selectHTML = `
          <div style="margin-bottom:10px; font-size:0.9rem; color:var(--text-secondary);">Select pharmacist to assign:</div>
          <select id="assign-user-select" style="width:100%; padding:8px; border:1px solid var(--border); border-radius:6px; font:inherit;">
            <option value="">-- Select --</option>
            ${options}
          </select>
        `;
        
        // Create a simple modal for selection
        const modal = document.createElement('div');
        modal.className = 'modal-overlay open';
        modal.innerHTML = `
          <div class="modal-box" style="max-width:400px;">
            <div class="modal-head">
              <h3>Assign Prescription</h3>
              <button type="button" class="btn ghost xs" onclick="this.closest('.modal-overlay').remove();" aria-label="Close">
                <i data-lucide="x"></i>
              </button>
            </div>
            ${selectHTML}
            <div class="modal-actions">
              <button type="button" class="btn" onclick="this.closest('.modal-overlay').remove();">Cancel</button>
              <button type="button" class="btn primary" id="confirm-assign-btn">
                <i data-lucide="user-plus"></i> Assign
              </button>
            </div>
          </div>
        `;
        document.body.appendChild(modal);
        initIcons();
        
        const confirmBtn = modal.querySelector('#confirm-assign-btn');
        const select = modal.querySelector('#assign-user-select');
        
        confirmBtn.addEventListener('click', async () => {
          const user = select.value.trim();
          if (!user) {
            toast({ title: 'No selection', message: 'Please select a pharmacist.', type: 'warning' });
            return;
          }
          
          modal.remove();
          
          try {
            const res = await fetchWithTimeout(`${API_BASE}/intakes/${intakeId}/assign`, {
              method: 'POST', headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ user })
            });
            if (!res.ok) {
              const err = await res.json().catch(() => ({}));
              let detail = typeof err.detail === 'string' ? err.detail : 'Assign failed';
              toast({ title: 'Assign failed', message: detail, type: 'error' });
              return;
            }
            toast({ title: 'Assigned', message: `Now assigned to ${user}.`, type: 'success' });
            await loadIntakes();
            await loadStatistics();
            refreshPatientSearchIfActive();
          } catch (e) {
            toast({ title: 'Network error', message: e.message || 'Assign failed', type: 'error' });
          }
        });
      } else {
        // Fallback to prompt if no users loaded
        const user = (prompt('Assign to user (name or initials):') || '').trim();
        if (!user) return;
        try {
          const res = await fetchWithTimeout(`${API_BASE}/intakes/${intakeId}/assign`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user })
          });
          if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            let detail = typeof err.detail === 'string' ? err.detail : 'Assign failed';
            toast({ title: 'Assign failed', message: detail, type: 'error' });
            return;
          }
          toast({ title: 'Assigned', message: `Now assigned to ${user}.`, type: 'success' });
          await loadIntakes();
          await loadStatistics();
          refreshPatientSearchIfActive();
        } catch (e) {
          toast({ title: 'Network error', message: e.message || 'Assign failed', type: 'error' });
        }
      }
    }
    async function dispenseMedication(intakeId) {
      if (!confirm('Mark as dispensed?')) return;
      try {
        const res = await fetchWithTimeout(`${API_BASE}/intakes/${intakeId}/dispense`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ dispensed: 'yes' })
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          toast({ title: 'Dispense failed', message: err.detail || `HTTP ${res.status}`, type: 'error' });
          return;
        }
        toast({ title: 'Dispensed', message: `Order #${intakeId} dispensed.`, type: 'success' });
        await loadIntakes();
        await loadStatistics();
        renderFilterBar();
        refreshPatientSearchIfActive();
      } catch (e) {
        toast({ title: 'Network error', message: e.message, type: 'error' });
      }
    }
    async function recheckInteractions(intakeId) {
      if (!confirm('Re-check drug interactions? This will re-run interaction detection and update counseling.')) return;
      try {
        const res = await fetchWithTimeout(`${API_BASE}/intakes/${intakeId}/check-interactions`, { method: 'POST' }, 120000);
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          toast({ title: 'Re-check failed', message: typeof err.detail === 'string' ? err.detail : 'Try again shortly.', type: 'error' });
          return;
        }
        toast({ title: 'Re-checked', message: 'Interactions and counseling refreshed.', type: 'success' });
        await loadIntakes();
        await loadStatistics();
        refreshPatientSearchIfActive();
      } catch (e) {
        const msg = e?.name === 'AbortError' ? 'Re-check timed out. Try again.' : (e.message || 'Network error');
        toast({ title: 'Re-check failed', message: msg, type: 'error' });
      }
    }

    /* ============ Counseling modal ============ */
    let counselingModalIntakeId = null;
    async function openCounselingEditor(intakeId) {
      try {
        const res = await fetchWithTimeout(`${API_BASE}/intakes/${intakeId}`);
        if (!res.ok) throw new Error('Could not load intake');
        const intake = await res.json();
        counselingModalIntakeId = intakeId;
        const name = intake.patient_name ? ` — ${intake.patient_name}` : '';
        document.getElementById('counseling-modal-title').textContent = `Edit counseling · #${intakeId}${name}`;
        document.getElementById('counseling-modal-text').value = intake.counseling_points || '';
        document.getElementById('counseling-modal').classList.add('open');
        setTimeout(() => document.getElementById('counseling-modal-text').focus(), 50);
      } catch (e) {
        toast({ title: 'Open failed', message: e.message || 'Could not open counseling editor.', type: 'error' });
      }
    }
    function closeCounselingModal() {
      document.getElementById('counseling-modal').classList.remove('open');
      counselingModalIntakeId = null;
    }
    async function saveCounselingFromModal() {
      const id = counselingModalIntakeId;
      if (!id) return;
      const text = document.getElementById('counseling-modal-text').value;
      try {
        const res = await fetchWithTimeout(`${API_BASE}/intakes/${id}/counseling`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ counseling_points: text }),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          toast({ title: 'Save failed', message: err.detail || `HTTP ${res.status}`, type: 'error' });
          return;
        }
        toast({ title: 'Counseling saved', type: 'success' });
        closeCounselingModal();
        await loadIntakes();
        refreshPatientSearchIfActive();
      } catch (e) {
        toast({ title: 'Save failed', message: e.message, type: 'error' });
      }
    }
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && document.getElementById('counseling-modal').classList.contains('open')) closeCounselingModal();
    });

    /* ============ Form submit ============ */
    document.getElementById('intake-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const submitBtn = document.getElementById('submit-btn');
      const submitBtnText = document.getElementById('submit-btn-text');
      submitBtn.disabled = true;
      submitBtnText.textContent = 'Creating…';

      const notesBase = document.getElementById('notes').value || '';
      const smoking = document.getElementById('smoking').value || '';
      const alcoholUse = document.getElementById('alcohol-use').value || '';
      const renalStatus = document.getElementById('renal-status').value || '';
      const hepaticStatus = document.getElementById('hepatic-status').value || '';
      const pregnancy = document.getElementById('pregnancy').value || '';

      const createPayload = {
        patient_name: document.getElementById('patient-name').value,
        patient_age: document.getElementById('patient-age').value ? parseInt(document.getElementById('patient-age').value) : null,
        patient_gender: document.getElementById('patient-gender').value || null,
        patient_phone: (document.getElementById('patient-phone').value || '').trim() || null,
        patient_allergies: document.getElementById('patient-allergies').value || null,
        medications: document.getElementById('medications').value,
        current_medications: document.getElementById('current-medications').value || null,
        notes: `${notesBase}${buildPatientContextString()}`.trim() || null,
      };
      const evalPayload = {
        ...createPayload,
        smoking: smoking || null,
        alcohol_use: alcoholUse || null,
        renal_status: renalStatus || null,
        hepatic_status: hepaticStatus || null,
        pregnancy: pregnancy || null,
      };

      const panel = document.getElementById('eval-panel');
      const loading = document.getElementById('eval-loading');
      const content = document.getElementById('eval-content');
      panel.style.display = '';
      loading.style.display = '';
      content.innerHTML = '';
      panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

      try {
        const createRes = await fetchWithTimeout(`${API_BASE}/intakes`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(createPayload),
        }, 45000);
        if (!createRes.ok) {
          const err = await createRes.json().catch(() => ({}));
          throw new Error(err.detail || 'Create failed');
        }
        submitBtnText.textContent = 'Analyzing…';
        const evalRes = await fetchWithTimeout(`${API_BASE}/intakes/evaluate`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(evalPayload),
        }, 15000);
        loading.style.display = 'none';
        if (evalRes.ok) {
          content.innerHTML = renderEvaluateResult(await evalRes.json());
          initIcons();
        } else {
          content.innerHTML = `<div class="error-state"><i data-lucide="alert-octagon"></i><div><strong>Analysis unavailable</strong><div>See intake card below for details.</div></div></div>`;
          initIcons();
        }

        document.getElementById('intake-form').reset();
        toast({ title: 'Intake created', message: `Order #${(await createRes.clone().json()).id || ''} added.`, type: 'success' });
        await loadIntakes();
        await loadStatistics();
        renderFilterBar();
        refreshPatientSearchIfActive();
      } catch (err) {
        loading.style.display = 'none';
        content.innerHTML = `<div class="error-state"><i data-lucide="alert-octagon"></i><div><strong>Error</strong><div>${esc(err.message)}</div></div></div>`;
        initIcons();
        toast({ title: 'Could not create intake', message: err.message, type: 'error' });
      } finally {
        submitBtn.disabled = false;
        submitBtnText.textContent = 'Create intake';
      }
    });

    /* ============ Logout & user chip ============ */
    async function logoutSession() {
      try { await fetch(`${API_BASE}/api/auth/logout`, { method: 'POST', credentials: 'include' }); }
      catch (e) {}
      window.location.href = '/login';
    }
    async function loadCurrentUser() {
      try {
        const res = await fetchWithTimeout(`${API_BASE}/api/auth/me`);
        if (!res.ok) return;
        const data = await res.json();
        if (data.user && data.user.username) {
          currentUsername = data.user.username;
          document.getElementById('user-name').textContent = data.user.username;
          document.getElementById('user-avatar').textContent = (data.user.username[0] || '?').toUpperCase();
        } else {
          document.getElementById('user-name').textContent = 'Guest';
          document.getElementById('user-avatar').textContent = '?';
        }
      } catch (e) {
        document.getElementById('user-name').textContent = 'Guest';
      }
    }

    /* ============ Init ============ */
    document.getElementById('logout-btn').addEventListener('click', logoutSession);
    document.getElementById('patient-search-input').addEventListener('input', schedulePatientSearch);
    bindPickupNotifyDelegation(document.getElementById('intake-list'));
    bindPickupNotifyDelegation(document.getElementById('patient-search-results'));
    document.getElementById('clear-search-btn').addEventListener('click', () => {
      const i = document.getElementById('patient-search-input');
      i.value = '';
      runPatientSearch();
    });

    setInterval(() => { loadStatistics().then(renderFilterBar); loadIntakes(); refreshPatientSearchIfActive(); }, 45000);
    /* Concurrency heartbeat: fires 3s after first paint, then every 20s. */
    setInterval(pollViewers, 20000);

    (async function init() {
      initIcons();
      renderStatsSkeleton();
      renderFilterBar();
      await Promise.all([loadStatistics().then(renderFilterBar), loadIntakes(), loadCurrentUser()]);
      setTimeout(pollViewers, 2500);
    })();
