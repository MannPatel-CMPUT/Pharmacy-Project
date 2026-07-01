    const API_BASE = window.location.origin;

    /* ============ Constants ============ */
    const WORKFLOW_STEPS = [
      { key: 'new',            label: 'Received'   },
      { key: 'triage',         label: 'Triage'     },
      { key: 'waiting_info',   label: 'Clarify'    },
      { key: 'ready_to_fill',  label: 'Fill queue' },
      { key: 'filled',         label: 'Pickup'     },
      { key: 'dispensed',      label: 'Dispensed'  },
      { key: 'completed',      label: 'Done'       },
    ];

    const STATUS_FILTERS = [
      { key: '',               label: 'All' },
      { key: 'new',            label: 'New' },
      { key: 'triage',         label: 'Triage' },
      { key: 'waiting_info',   label: 'Waiting' },
      { key: 'ready_to_fill',  label: 'Ready to fill' },
      { key: 'filled',         label: 'Ready for pickup' },
      { key: 'dispensed',      label: 'Dispensed' },
      { key: 'completed',      label: 'Completed' },
    ];

    const SEV_ICON = {
      contraindicated: 'octagon-alert',
      major: 'triangle-alert',
      moderate: 'alert-circle',
      minor: 'info',
      unknown: 'help-circle',
    };

    const _RISK_MAP = { contraindicated:'Very High', major:'High', moderate:'Moderate', minor:'Low', unknown:'Unknown' };
    const _REC_MAP = {
      contraindicated: 'Avoid this combination. Seek immediate medical advice.',
      major: 'Avoid unless specifically directed by the prescriber. Requires close monitoring.',
      moderate: 'Use with caution. Monitor closely and counsel the patient.',
      minor: 'Generally safe; monitor for minor side effects.',
      unknown: 'Insufficient data — consult the prescriber or pharmacist.',
    };
    const _SEV_ORDER = ['contraindicated','major','moderate','minor','unknown'];

    let activeStatusFilter = '';
    let currentStats = null;
    let allUsers = [];
    let currentUsername = null;
    /* Cache the latest intake payloads so the PDF exporter (and future features
       like the audit-trail page) can look them up by id without a re-fetch. */
    const intakesById = new Map();

    function _riskClass(risk) {
      return { 'None':'risk-none','Low':'risk-low','Moderate':'risk-moderate','High':'risk-high','Very High':'risk-veryhigh' }[risk] || 'risk-unknown';
    }
    function _riskIcon(risk) {
      return { 'None':'check-circle-2','Low':'info','Moderate':'alert-circle','High':'triangle-alert','Very High':'octagon-alert' }[risk] || 'help-circle';
    }
    function fmt(v) { return (v === null || v === undefined || v === '') ? '—' : v; }
    function esc(s) {
      return String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    }
    function initIcons() {
      try { window.lucide && window.lucide.createIcons(); } catch (_) { /* icons are best-effort */ }
    }

    /* ============ Toasts ============ */
    function toast({ title, message = '', type = 'info', timeout = 4500 } = {}) {
      const stack = document.getElementById('toast-stack');
      const el = document.createElement('div');
      el.className = `toast ${type}`;
      const icon = type === 'success' ? 'check-circle-2'
                 : type === 'error'   ? 'alert-octagon'
                 : type === 'warning' ? 'alert-triangle'
                 : 'info';
      el.innerHTML = `
        <i data-lucide="${icon}"></i>
        <div class="toast-body">
          ${title ? `<strong>${esc(title)}</strong>` : ''}
          ${message ? esc(message) : ''}
        </div>
        <button class="toast-close" aria-label="Dismiss"><i data-lucide="x"></i></button>
      `;
      stack.appendChild(el);
      initIcons();
      const close = () => { el.style.animation = 'toastIn 0.18s ease-out reverse both'; setTimeout(() => el.remove(), 200); };
      el.querySelector('.toast-close').addEventListener('click', close);
      if (timeout) setTimeout(close, timeout);
    }

    /* ============ Workflow stepper ============ */
    function renderWorkflowTrack(status) {
      const idx = WORKFLOW_STEPS.findIndex(s => s.key === status);
      return WORKFLOW_STEPS.map((s, i) => {
        let cls = 'step';
        if (i < idx) cls += ' done';
        else if (i === idx) cls += s.key === 'filled' ? ' pickup' : ' active';
        return `<span class="${cls}">${esc(s.label)}</span>`;
      }).join('<span class="sep">›</span>');
    }

    /* ============ Pickup messages / actions ============ */
    function pickupReadyMessage(intakeId, patientName) {
      const who = (patientName && String(patientName).trim()) || 'Patient';
      return `Hi ${who}, your prescription (order #${intakeId}) is ready for pickup at the pharmacy. Please bring a valid ID. Thank you.`;
    }
    function notifyPickupBrowser(intakeId, patientName) {
      if (!('Notification' in window)) {
        toast({ title: 'Not supported', message: 'This browser does not support desktop notifications. Use Copy or SMS/Email instead.', type: 'warning' });
        return;
      }
      const run = () => {
        try {
          new Notification('Prescription ready for pickup', { body: pickupReadyMessage(intakeId, patientName), tag: `pickup-${intakeId}` });
        } catch (e) { toast({ title: 'Notification error', message: String(e.message || e), type: 'error' }); }
      };
      if (Notification.permission === 'granted') return run();
      if (Notification.permission === 'denied') {
        toast({ title: 'Blocked', message: 'Notifications are blocked. Enable them in browser settings, or use Copy/SMS/Email.', type: 'warning' });
        return;
      }
      Notification.requestPermission().then((p) => {
        if (p === 'granted') run();
        else toast({ title: 'Permission needed', message: 'Notification permission not granted.', type: 'warning' });
      });
    }
    function copyPickupMessage(intakeId, patientName) {
      const text = pickupReadyMessage(intakeId, patientName);
      const ok = () => toast({ title: 'Copied', message: 'Pickup message ready to paste.', type: 'success' });
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(ok).catch(() => fallbackCopy(text, ok));
      } else fallbackCopy(text, ok);
    }
    function fallbackCopy(text, onok) {
      const ta = document.createElement('textarea');
      ta.value = text; document.body.appendChild(ta); ta.select();
      try { document.execCommand('copy'); onok && onok(); }
      catch { prompt('Copy this message:', text); }
      document.body.removeChild(ta);
    }
    function openPickupSms(intakeId, patientName) {
      const body = encodeURIComponent(pickupReadyMessage(intakeId, patientName));
      window.location.href = `sms:?body=${body}`;
    }
    function openPickupEmail(intakeId, patientName) {
      const subj = encodeURIComponent(`Prescription ready for pickup — order #${intakeId}`);
      const body = encodeURIComponent(pickupReadyMessage(intakeId, patientName));
      window.location.href = `mailto:?subject=${subj}&body=${body}`;
    }

    /** E.164 digits only for wa.me (no +). 10-digit NA numbers default to country code 1. */
    function digitsForWhatsApp(phoneRaw) {
      const d = String(phoneRaw || '').replace(/\D/g, '');
      if (!d) return '';
      if (d.length === 10) return '1' + d;
      return d;
    }
    function bindPickupNotifyDelegation(root) {
      if (!root || root.dataset.pickupDelegateBound) return;
      root.dataset.pickupDelegateBound = '1';
      root.addEventListener('click', (e) => {
        const btn = e.target.closest('[data-pickup-action]');
        if (!btn || !root.contains(btn)) return;
        const action = btn.getAttribute('data-pickup-action');
        const id = parseInt(btn.getAttribute('data-intake-id'), 10);
        const patientName = btn.getAttribute('data-patient-name') || '';
        if (Number.isNaN(id)) return;
        if (action === 'browser') {
          e.preventDefault();
          notifyPickupBrowser(id, patientName);
        } else if (action === 'copy') {
          e.preventDefault();
          copyPickupMessage(id, patientName);
        } else if (action === 'sms') {
          e.preventDefault();
          openPickupSms(id, patientName);
        } else if (action === 'email') {
          e.preventDefault();
          openPickupEmail(id, patientName);
        }
      });
    }

    /* ============ Patient context (notes) ============ */
    function buildPatientContextString() {
      const ctx = {
        patient_gender: document.getElementById('patient-gender').value || 'unknown',
        renal_status: document.getElementById('renal-status').value || 'unknown',
        hepatic_status: document.getElementById('hepatic-status').value || 'unknown',
        alcohol_use: document.getElementById('alcohol-use').value || 'unknown',
        pregnancy: document.getElementById('pregnancy').value || 'unknown',
        smoking: document.getElementById('smoking').value || 'unknown'
      };
      return `\n\n[Patient Context]\n${Object.entries(ctx).map(([k,v]) => `${k}: ${v}`).join('\n')}`;
    }
    function _parsePatientContext(notes) {
      if (!notes) return {};
      const m = notes.match(/\[Patient Context\]([\s\S]*)/);
      if (!m) return {};
      const ctx = {};
      for (const line of m[1].trim().split('\n')) {
        const idx = line.indexOf(':');
        if (idx > -1) ctx[line.slice(0, idx).trim()] = line.slice(idx + 1).trim();
      }
      return ctx;
    }

    /* ============ Fetch ============ */
    async function fetchWithTimeout(url, options = {}, timeout = 10000) {
      const controller = new AbortController();
      const t = setTimeout(() => controller.abort(), timeout);
      try {
        const res = await fetch(url, { ...options, signal: controller.signal, cache: options.cache ?? 'no-store' });
        clearTimeout(t); return res;
      } catch (e) { clearTimeout(t); throw e; }
    }

    /* ============ Allergy / lifestyle helpers (front-end mirrors) ============ */
    function _tokenize(text) { return (text || '').toLowerCase().split(/[,;\s/]+/).filter(t => t.length > 2); }
    function computeAllergyWarnings(allergies, medications, currentMedications) {
      if (!allergies) return [];
      const nkda = new Set(['nkda','no known drug allergies','none','nka','no allergies','no known allergies','nil']);
      if (nkda.has(allergies.trim().toLowerCase())) return [];
      const families = {
        penicillin: ['amoxicillin','ampicillin','piperacillin','nafcillin','oxacillin'],
        cephalosporin: ['cephalexin','cefazolin','ceftriaxone','cefdinir','cefuroxime'],
        sulfa: ['sulfamethoxazole','trimethoprim','sulfadiazine','sulfasalazine'],
        nsaid: ['ibuprofen','naproxen','aspirin','diclofenac','indomethacin','celecoxib'],
        statin: ['atorvastatin','simvastatin','rosuvastatin','pravastatin','lovastatin'],
        opioid: ['hydrocodone','oxycodone','morphine','codeine','tramadol'],
        benzodiazepine: ['alprazolam','lorazepam','diazepam','clonazepam'],
      };
      const allergyTokens = _tokenize(allergies);
      const medTokens = _tokenize([medications, currentMedications].filter(Boolean).join(' '));
      const warnings = [], flagged = new Set();
      for (const allergy of allergyTokens) {
        if (nkda.has(allergy) || allergy.length < 3) continue;
        for (const med of medTokens) {
          if (allergy.includes(med) || med.includes(allergy)) {
            const key = `d|${allergy}|${med}`;
            if (!flagged.has(key)) { flagged.add(key); warnings.push(`Allergy to '${allergy}' may be relevant to '${med}' — verify before dispensing.`); }
          }
        }
        for (const [family, members] of Object.entries(families)) {
          if (allergy === family || family.includes(allergy) || allergy.includes(family)) {
            for (const member of members) {
              for (const med of medTokens) {
                if (med.includes(member) || member.includes(med)) {
                  const key = `f|${family}|${med}`;
                  if (!flagged.has(key)) { flagged.add(key); warnings.push(`Allergy to '${allergy}' (${family} family): '${med}' may be related — confirm with prescriber.`); }
                }
              }
            }
          }
        }
      }
      return warnings;
    }
    const _FEMALE = new Set(['female','f','woman','girl']);
    const _MALE   = new Set(['male','m','man','boy']);
    const _TERATOGEN_RE = /methotrexate|isotretinoin|leflunomide|thalidomide|azathioprine|valproat|lithium|warfarin|ribavirin|mycophenolate|bosentan|finasteride|dutasteride/;
    const _MALE_MED_RE  = /sildenafil|tadalafil|vardenafil|finasteride|dutasteride|testosterone|tamsulosin|alfuzosin/;
    function computeLifestyleWarnings(ctx, medications, currentMedications) {
      const warnings = [], seen = new Set();
      const meds = [medications, currentMedications].filter(Boolean).join(' ').toLowerCase();
      const add = w => { if (!seen.has(w)) { seen.add(w); warnings.push(w); } };
      const smoking = (ctx.smoking || '').toLowerCase();
      const alcohol = (ctx.alcohol_use || '').toLowerCase();
      const renal = (ctx.renal_status || '').toLowerCase();
      const hepatic = (ctx.hepatic_status || '').toLowerCase();
      const preg = (ctx.pregnancy || '').toLowerCase();
      const gender = (ctx.patient_gender || '').toLowerCase();
      if (['yes','former'].includes(smoking))
        add('Smoking can affect metabolism of many medications and may reduce effectiveness. Dose adjustments may be needed.');
      if (['regular','occasional'].includes(alcohol))
        add('Alcohol use may increase risk of side effects (drowsiness, dizziness, stomach upset).');
      if (alcohol === 'regular' && /warfarin|metronidazole|isoniazid|acetaminophen/.test(meds))
        add('Regular alcohol use with one or more of these medications may cause serious harm — bleeding or liver damage risk.');
      if (alcohol && /alprazolam|lorazepam|diazepam|clonazepam|zolpidem|hydrocodone|oxycodone|morphine|codeine|tramadol/.test(meds))
        add('Alcohol with sedative or pain medications can cause dangerous over-sedation. Avoid alcohol entirely.');
      if (['mild','moderate','severe'].includes(renal))
        add(`Kidney impairment (${renal}) may affect medication dosing and clearance — extra monitoring may be required.`);
      if (['mild','moderate','severe'].includes(hepatic))
        add(`Liver impairment (${hepatic}) affects drug metabolism — some medications may be less effective or more toxic.`);
      if (preg === 'yes')
        add('Confirm all medications are safe during pregnancy with the prescriber.');
      if (_FEMALE.has(gender)) {
        if (_TERATOGEN_RE.test(meds))
          add('Gender-specific (female): one or more medications may be teratogenic. Confirm contraception status and safety with the prescriber.');
        if (preg === 'yes')
          add('Pregnancy confirmed for a female patient — ensure all medications are pregnancy-safe.');
      }
      if (_MALE.has(gender)) {
        if (_MALE_MED_RE.test(meds))
          add('Gender-specific (male): one or more medications are indicated specifically for male patients — verify indication and dosing.');
        if (preg === 'yes')
          add('Pregnancy recorded for a patient identified as male — verify the gender or pregnancy field before dispensing.');
      }
      return warnings;
    }

    function parseCounselingPoints(text = '') {
      return text.split('\n').map(line => line.trim()).filter(line => line.length > 0).map(line => line.replace(/^[•\-*]\s*/, ''));
    }

