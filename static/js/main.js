/**
 * main.js — Insurance CMS front-end logic
 */

/* ── Theme ──────────────────────────────────────────────────── */
const root = document.documentElement;
const savedTheme = localStorage.getItem('theme') || 'light';
root.setAttribute('data-theme', savedTheme);

function toggleTheme() {
  const current = root.getAttribute('data-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  root.setAttribute('data-theme', next);
  localStorage.setItem('theme', next);
  const btn = document.getElementById('themeToggle');
  if (btn) btn.textContent = next === 'dark' ? '☀️' : '🌙';
}

document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('themeToggle');
  if (btn) btn.textContent = savedTheme === 'dark' ? '☀️' : '🌙';
});

/* ── Mobile sidebar ─────────────────────────────────────────── */
function toggleSidebar() {
  document.querySelector('.sidebar')?.classList.toggle('open');
  document.querySelector('.sidebar-overlay')?.classList.toggle('open');
}
document.addEventListener('click', e => {
  if (e.target.classList.contains('sidebar-overlay')) toggleSidebar();
});

/* ── Toast ───────────────────────────────────────────────────── */
function showToast(message, type = 'success', duration = 3500) {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    document.body.appendChild(container);
  }
  const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${icons[type] || '•'}</span><span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.animation = 'slideOut .3s ease forwards';
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

/* ── Modal helpers ───────────────────────────────────────────── */
function openModal(id) {
  document.getElementById(id)?.classList.add('open');
  document.body.style.overflow = 'hidden';
}
function closeModal(id) {
  document.getElementById(id)?.classList.remove('open');
  document.body.style.overflow = '';
}
// Close on overlay click
document.addEventListener('click', e => {
  if (e.target.classList.contains('modal-overlay')) {
    e.target.classList.remove('open');
    document.body.style.overflow = '';
  }
});
// Close on Escape
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal-overlay.open').forEach(m => {
      m.classList.remove('open');
      document.body.style.overflow = '';
    });
  }
});

/* ── Tabs ─────────────────────────────────────────────────────── */
function switchTab(el, contentId) {
  const parent = el.closest('.tabs-container') || el.parentElement.parentElement;
  parent.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  parent.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
  el.classList.add('active');
  document.getElementById(contentId)?.classList.add('active');
}

/* ── Confirm dialog ──────────────────────────────────────────── */
function confirmAction(message, callback) {
  if (window.confirm(message)) callback();
}

/* ── AJAX helpers ────────────────────────────────────────────── */
async function apiGet(url) {
  const res = await fetch(url, { credentials: 'same-origin' });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function apiPost(url, formData) {
  const res = await fetch(url, {
    method: 'POST', body: formData, credentials: 'same-origin'
  });
  return res.json();
}

async function apiPut(url, formData) {
  const res = await fetch(url, {
    method: 'PUT', body: formData, credentials: 'same-origin'
  });
  return res.json();
}

async function apiDelete(url) {
  const res = await fetch(url, {
    method: 'DELETE', credentials: 'same-origin'
  });
  return res.json();
}

/* ── Client Management ───────────────────────────────────────── */
let editingClientId = null;

function openAddClient() {
  editingClientId = null;
  document.getElementById('clientModalTitle').textContent = 'Add New Client';
  document.getElementById('clientForm').reset();
  openModal('clientModal');
}

async function openEditClient(id) {
  editingClientId = id;
  try {
    const data = await apiGet(`/api/clients/${id}`);
    const form = document.getElementById('clientForm');
    Object.keys(data).forEach(key => {
      const el = form.elements[key];
      if (el) el.value = data[key] ?? '';
    });
    document.getElementById('clientModalTitle').textContent = 'Edit Client';
    openModal('clientModal');
  } catch (e) {
    showToast('Failed to load client data.', 'error');
  }
}

async function saveClient(e) {
  e.preventDefault();
  const form = document.getElementById('clientForm');
  const fd   = new FormData(form);
  // Button lives outside <form> in modal-footer, so use getElementById
  const btn  = document.getElementById('saveClientBtn');
  if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> Saving…'; }

  try {
    let result;
    if (editingClientId) {
      result = await apiPut(`/api/clients/${editingClientId}`, fd);
    } else {
      result = await apiPost('/api/clients', fd);
    }
    if (result.success) {
      showToast(result.message);
      closeModal('clientModal');
      setTimeout(() => location.reload(), 700);
    } else {
      showToast(result.error || 'Save failed.', 'error');
    }
  } catch (err) {
    showToast('Network error.', 'error');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '💾 Save Client'; }
  }
}

async function deleteClient(id, name) {
  confirmAction(`Delete client "${name}"? This cannot be undone.`, async () => {
    try {
      const result = await apiDelete(`/api/clients/${id}`);
      if (result.success) {
        showToast(result.message);
        document.getElementById(`row-${id}`)?.remove();
      } else {
        showToast(result.error || 'Delete failed.', 'error');
      }
    } catch {
      showToast('Network error.', 'error');
    }
  });
}

/* ── Universal Search ────────────────────────────────────────── */
let searchTimer = null;

function initSearch(inputId, resultsId) {
  const input   = document.getElementById(inputId);
  const results = document.getElementById(resultsId);
  if (!input || !results) return;

  input.addEventListener('input', () => {
    clearTimeout(searchTimer);
    const q = input.value.trim();
    if (q.length < 2) {
      results.innerHTML = '';
      return;
    }
    searchTimer = setTimeout(() => performSearch(q, results), 280);
  });
}

async function performSearch(q, container) {
  container.innerHTML = '<tr><td colspan="8" class="table-empty"><div class="spinner" style="margin:auto"></div></td></tr>';
  try {
    const data = await apiGet(`/api/search?q=${encodeURIComponent(q)}`);
    renderSearchResults(data, container, q);
  } catch {
    container.innerHTML = '<tr><td colspan="8" class="table-empty">Search failed.</td></tr>';
  }
}

function renderSearchResults(data, tbody, q) {
  const count = document.getElementById('searchCount');
  if (count) count.textContent = `${data.length} result${data.length !== 1 ? 's' : ''} found`;

  if (!data.length) {
    tbody.innerHTML = `<tr><td colspan="8" class="table-empty">No clients found for "<strong>${esc(q)}</strong>"</td></tr>`;
    return;
  }

  tbody.innerHTML = data.map(c => `
    <tr>
      <td><a href="/clients/${c.id}" class="font-semibold" style="color:var(--primary);text-decoration:none">${esc(c.full_name)}</a></td>
      <td>${esc(c.phone||'–')}</td>
      <td>${esc(c.email||'–')}</td>
      <td>${esc(c.policy_number||'–')}</td>
      <td>${esc(c.policy_type||'–')}</td>
      <td>${esc(c.vehicle_number||'–')}</td>
      <td>${renewalBadge(c.renewal_date)}</td>
      <td>
        <div class="flex gap-2">
          <a href="/clients/${c.id}" class="btn-icon" title="View">👁️</a>
          <button class="btn-icon" onclick="openEditClient(${c.id})" title="Edit">✏️</button>
          <button class="btn-icon danger" onclick="deleteClient(${c.id},'${esc(c.full_name)}')" title="Delete">🗑️</button>
        </div>
      </td>
    </tr>
  `).join('');
}

function renewalBadge(dateStr) {
  if (!dateStr) return '<span class="badge badge-secondary">–</span>';
  const days = daysUntil(dateStr);
  if (days < 0)  return `<span class="badge badge-expired">Expired</span>`;
  if (days <= 30) return `<span class="badge badge-danger">Due in ${days}d</span>`;
  if (days <= 60) return `<span class="badge badge-warning">Due in ${days}d</span>`;
  return `<span class="badge badge-success">Active</span>`;
}

function daysUntil(dateStr) {
  const today  = new Date(); today.setHours(0,0,0,0);
  const target = new Date(dateStr);
  return Math.round((target - today) / 86400000);
}

function esc(str) {
  return String(str ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

/* ── Document Upload ─────────────────────────────────────────── */
function initUploadZone(zoneId, inputId) {
  const zone  = document.getElementById(zoneId);
  const input = document.getElementById(inputId);
  if (!zone || !input) return;

  zone.addEventListener('click', () => input.click());
  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', e => {
    e.preventDefault();
    zone.classList.remove('drag-over');
    if (e.dataTransfer.files[0]) {
      input.files = e.dataTransfer.files;
      zone.querySelector('p').textContent = e.dataTransfer.files[0].name;
    }
  });
  input.addEventListener('change', () => {
    if (input.files[0]) zone.querySelector('p').textContent = input.files[0].name;
  });
}

async function uploadDocument(clientId) {
  const form    = document.getElementById('uploadForm');
  const fd      = new FormData(form);
  const fileInput = document.getElementById('docFile');
  if (!fileInput.files[0]) { showToast('Please select a file.', 'warning'); return; }

  fd.append('client_id', clientId);
  fd.append('file', fileInput.files[0]);

  const btn = document.getElementById('uploadBtn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Uploading…';

  try {
    const result = await apiPost('/api/documents/upload', fd);
    if (result.success) {
      showToast('Document uploaded!');
      closeModal('uploadModal');
      setTimeout(() => location.reload(), 700);
    } else {
      showToast(result.error || 'Upload failed.', 'error');
    }
  } catch {
    showToast('Network error.', 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Upload';
  }
}

async function deleteDocument(docId) {
  confirmAction('Delete this document permanently?', async () => {
    try {
      const result = await apiDelete(`/api/documents/${docId}`);
      if (result.success) {
        showToast('Document deleted.');
        document.getElementById(`doc-${docId}`)?.remove();
      } else {
        showToast(result.error || 'Delete failed.', 'error');
      }
    } catch {
      showToast('Network error.', 'error');
    }
  });
}

/* ── Topbar quick-search redirect ────────────────────────────── */
function topbarSearch(e) {
  if (e.key === 'Enter') {
    const q = e.target.value.trim();
    if (q) window.location.href = `/search?q=${encodeURIComponent(q)}`;
  }
}

/* ── Init on DOM ready ───────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  // Client form submit
  document.getElementById('clientForm')?.addEventListener('submit', saveClient);

  // Search page
  initSearch('searchInput', 'searchResultsBody');

  // Pre-fill search if ?q= param present
  const urlQ = new URLSearchParams(location.search).get('q');
  const inp  = document.getElementById('searchInput');
  if (urlQ && inp) {
    inp.value = urlQ;
    inp.dispatchEvent(new Event('input'));
  }

  // Upload zone
  initUploadZone('uploadZone', 'docFile');
});
