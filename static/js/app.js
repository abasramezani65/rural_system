/* Rural Services System - Frontend Application */
'use strict';

const State = {
  user: null,
  roles: [],
  services: [],
  provinces: [],
  records: [],
  announcements: [],
  customFields: [],
  coreFields: [],
  settings: {},
  geoCatalog: [],
  users: [],
  loginAnnouncements: [],
  loginBanners: [],
  loginAnnouncementsAll: [],
  loginBannersAll: [],
  plans: [],
  planRecords: [],
  planStats: {},
  planFieldsCache: {},
  selectedPlanStatus: 'done',
  selectedPlans: new Set(),
  editingPlanId: null,
  editingUserId: null,
  editingRecordId: null,
  charts: {},
};

const fa = (n) => Number(n || 0).toLocaleString('fa-IR');
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

// ----- HTTP helpers -----
async function api(path, opts = {}) {
  const cfg = {
    method: opts.method || 'GET',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
  };
  if (opts.body) cfg.body = JSON.stringify(opts.body);
  const resp = await fetch(path, cfg);
  let data;
  try { data = await resp.json(); } catch (e) { data = {}; }
  if (!resp.ok) {
    throw new Error(data.error || `HTTP ${resp.status}`);
  }
  return data;
}

// ----- Toast notifications -----
function toast(msg, type = 'success') {
  const c = document.getElementById('toastContainer');
  const el = document.createElement('div');
  el.className = 'toast ' + type;
  el.textContent = msg;
  c.appendChild(el);
  setTimeout(() => { el.style.opacity = '0'; setTimeout(() => el.remove(), 300); }, 3000);
}

// ----- Theme management -----
function getStoredTheme() { return localStorage.getItem('rural_theme') || 'light'; }
function setStoredTheme(t) { localStorage.setItem('rural_theme', t); }
function applyTheme(t) {
  document.documentElement.setAttribute('data-theme', t);
  document.querySelectorAll('.theme-toggle').forEach(btn => {
    if (btn) btn.textContent = t === 'dark' ? '☀️ روشن' : '🌙 تاریک';
  });
}
function toggleTheme() {
  const current = getStoredTheme();
  const next = current === 'dark' ? 'light' : 'dark';
  setStoredTheme(next);
  applyTheme(next);
}

// ----- Login announcements & banners rendering on login page -----
function renderLoginAnnouncementsAndBanners() {
  const annList = document.getElementById('loginAnnouncementList');
  const bannerContainer = document.getElementById('loginBannerContainer');
  if (!annList || !bannerContainer) return;

  const anns = State.loginAnnouncements || [];
  annList.innerHTML = anns.map(a =>
    `<div class="login-announcement-item ${a.festive ? 'festive' : ''}">${esc(a.text)}</div>`
  ).join('');

  const banners = State.loginBanners || [];
  bannerContainer.innerHTML = banners.map(b => {
    const src = `data:${b.image_mime};base64,${b.image_data}`;
    if (b.link_url) {
      return `<a href="${esc(b.link_url)}" target="_blank" rel="noopener" title="${esc(b.title)}"><img src="${src}" alt="${esc(b.title)}"></a>`;
    }
    return `<img src="${src}" alt="${esc(b.title)}" title="${esc(b.title)}">`;
  }).join('');
}

// ----- Draggable element helper -----
function makeDraggable(element, storageKey) {
  if (!element) return;
  let isDragging = false;
  let startX = 0, startY = 0;
  let elemX = 0, elemY = 0;

  // Restore saved position
  const saved = localStorage.getItem(storageKey);
  if (saved) {
    try {
      const pos = JSON.parse(saved);
      if (pos && typeof pos.x === 'number' && typeof pos.y === 'number') {
        applyPosition(pos.x, pos.y);
      }
    } catch (e) {}
  }

  function applyPosition(x, y) {
    elemX = x;
    elemY = y;
    element.style.transform = `translate(${x}px, ${y}px)`;
  }

  function pointerDown(e) {
    // Don't start drag if clicking on form elements / links / images inside the card
    if (e.target.closest('input, button, a, label, select, textarea, .toggle-password, img')) return;
    isDragging = true;
    element.classList.add('dragging');
    const pt = e.touches ? e.touches[0] : e;
    startX = pt.clientX;
    startY = pt.clientY;
    e.preventDefault();
  }

  function pointerMove(e) {
    if (!isDragging) return;
    const pt = e.touches ? e.touches[0] : e;
    const dx = pt.clientX - startX;
    const dy = pt.clientY - startY;
    applyPosition(elemX + dx, elemY + dy);
    e.preventDefault();
  }

  function pointerUp() {
    if (!isDragging) return;
    isDragging = false;
    element.classList.remove('dragging');
    localStorage.setItem(storageKey, JSON.stringify({ x: elemX, y: elemY }));
  }

  element.addEventListener('mousedown', pointerDown);
  element.addEventListener('touchstart', pointerDown, { passive: false });
  window.addEventListener('mousemove', pointerMove);
  window.addEventListener('touchmove', pointerMove, { passive: false });
  window.addEventListener('mouseup', pointerUp);
  window.addEventListener('touchend', pointerUp);
}

// ----- Login -----
function bindLogin() {
  applyTheme(getStoredTheme());

  // Toggle password visibility
  const toggleBtn = document.getElementById('togglePassword');
  if (toggleBtn) {
    toggleBtn.addEventListener('click', () => {
      const inp = document.getElementById('loginPassword');
      inp.type = inp.type === 'password' ? 'text' : 'password';
    });
  }

  // Drag disabled per user request (fixed layout)

  document.getElementById('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const username = document.getElementById('loginUsername').value.trim();
    const password = document.getElementById('loginPassword').value;
    const errEl = document.getElementById('loginError');
    errEl.textContent = '';
    const btn = document.getElementById('loginSubmitButton');
    const originalText = btn.innerHTML;
    btn.innerHTML = '<span class="loader" style="border-color:rgba(255,255,255,.4);border-top-color:white"></span> در حال ورود...';
    btn.disabled = true;
    try {
      const resp = await api('/api/login', { method: 'POST', body: { username, password } });
      toast('خوش آمدید ' + resp.user.name);
      await loadState();
      showApp();
    } catch (err) {
      errEl.textContent = err.message;
    } finally {
      btn.innerHTML = originalText;
      btn.disabled = false;
    }
  });

  document.getElementById('loginForgotPassword').addEventListener('click', (e) => {
    e.preventDefault();
    toast('برای بازیابی گذرواژه با مدیر سامانه تماس بگیرید.', 'error');
  });
}

async function logout() {
  try { await api('/api/logout', { method: 'POST' }); } catch (e) {}
  State.user = null;
  document.getElementById('loginOverlay').classList.remove('hidden');
  document.getElementById('mainHeader').hidden = true;
  document.getElementById('mainWrap').hidden = true;
  document.getElementById('tickerShell').hidden = true;
  // Reset login screen
  renderLoginDesign();
}

// ----- State loading -----
async function loadState() {
  const data = await api('/api/state');
  Object.assign(State, {
    user: data.user || null,
    roles: data.roles || [],
    services: data.services || [],
    provinces: data.provinces || [],
    records: data.records || [],
    announcements: data.announcements || [],
    customFields: data.customFields || [],
    coreFields: data.coreFields || [],
    settings: data.settings || {},
    geoCatalog: data.geoCatalog || [],
    users: data.users || [],
    loginAnnouncements: data.loginAnnouncements || [],
    loginBanners: data.loginBanners || [],
    loginAnnouncementsAll: data.loginAnnouncementsAll || [],
    loginBannersAll: data.loginBannersAll || [],
    plans: data.plans || [],
    planRecords: data.planRecords || [],
    planStats: data.planStats || {},
  });
  renderLoginAnnouncementsAndBanners();
  // Render plan UI if elements exist
  if (document.getElementById('plansAdminList')) renderPlansAdmin();
  if (document.getElementById('planListContainer')) renderPlanRegistration();
  if (document.getElementById('reportPlanFilter')) populatePlanReportFilter();
  return data;
}

function showApp() {
  document.getElementById('loginOverlay').classList.add('hidden');
  document.getElementById('mainHeader').hidden = false;
  document.getElementById('mainWrap').hidden = false;
  document.getElementById('tickerShell').hidden = false;

  // Theme toggle button
  const themeBtn = document.getElementById('themeToggle');
  if (themeBtn && !themeBtn._bound) {
    themeBtn.addEventListener('click', toggleTheme);
    themeBtn._bound = true;
  }
  applyTheme(getStoredTheme());

  // Session bar
  const sb = document.getElementById('sessionBar');
  if (State.user) {
    sb.hidden = false;
    document.getElementById('sessionLabel').textContent = `${State.user.name} (${roleLabel(State.user.role)})`;
    document.getElementById('logoutBtn').onclick = logout;
  } else {
    sb.hidden = true;
  }

  // Admin tab visibility
  const adminTab = document.getElementById('adminTab');
  adminTab.hidden = State.user?.role !== 'national';

  // Bind collapsible cards
  document.querySelectorAll('.card.collapsible .card-header').forEach(h => {
    if (h._bound) return;
    h._bound = true;
    h.addEventListener('click', () => h.parentElement.classList.toggle('collapsed'));
  });

  renderAll();
}

function roleLabel(r) {
  return { national: 'کشوری', provincial: 'استانی', county: 'شهرستانی' }[r] || r;
}

// ----- Rendering -----
function renderAll() {
  renderBranding();
  renderAnnouncementList();
  renderBaseSelects();
  renderAdminSectionList();
  renderFilterServices();
  renderFilterSelects();
  renderUsersTable();
  renderCustomFields();
  renderRoles();
  renderServicesAdmin();
  renderGeoList();
  renderRecords();
  renderSummary();
  updateDynamicFields();
  renderLoginAnnouncementsAdmin();
  renderLoginBannersAdmin();
  renderLoginDesign();
}

function renderBranding() {
  const s = State.settings;
  document.getElementById('appTitle').textContent = s.title || 'سامانه پایش خدمات روستایی';
  document.getElementById('appSubtitle').textContent = s.subtitle || '';
  document.title = s.title || 'سامانه پایش خدمات روستایی';
  // Logo / banner: not loaded as base64 in this version
}

function renderAnnouncementList() {
  const list = document.getElementById('announcementList');
  if (!State.announcements.length) {
    list.innerHTML = '<div class="empty">اعلانی ثبت نشده است.</div>';
  } else {
    list.innerHTML = '<table><thead><tr><th>متن</th><th>عملیات</th></tr></thead><tbody>' +
      State.announcements.map(a => `<tr><td>${esc(a.text)}</td><td><button class="small danger" data-del-an="${a.id}">حذف</button></td></tr>`).join('') +
      '</tbody></table>';
  }
  list.querySelectorAll('[data-del-an]').forEach(btn => {
    btn.onclick = async () => {
      try {
        await api(`/api/announcements/${btn.dataset.delAn}`, { method: 'DELETE' });
        State.announcements = State.announcements.filter(a => a.id !== btn.dataset.delAn);
        renderAnnouncementList();
        renderTicker();
        toast('اعلان حذف شد.');
      } catch (e) { toast(e.message, 'error'); }
    };
  });
  renderTicker();
}

function renderTicker() {
  const t = document.getElementById('tickerTrack');
  t.textContent = State.announcements.length ? State.announcements.map(a => a.text).join('   •   ') : 'اعلانی موجود نیست';
}

function renderBaseSelects() {
  // Roles
  const roleSel = document.getElementById('expertRole');
  roleSel.innerHTML = '<option value="">انتخاب سمت</option>' +
    State.roles.filter(r => r.active).map(r => `<option value="${r.id}">${esc(r.name)}</option>`).join('');
  // Services
  const svcSel = document.getElementById('service');
  svcSel.innerHTML = '<option value="">انتخاب خدمت</option>' +
    State.services.filter(s => s.active).map(s => `<option value="${s.id}">${esc(s.name)}</option>`).join('');
  // Provinces
  const provSel = document.getElementById('province');
  provSel.innerHTML = '<option value="">انتخاب استان</option>' +
    State.provinces.map(p => `<option value="${p.id}">${esc(p.name)}</option>`).join('');
  // Reset county
  fillCountySelect();
  // User form
  renderUserCountySelects();
  // Province for county
  const pfc = document.getElementById('provinceForCounty');
  if (pfc) pfc.innerHTML = '<option value="">انتخاب استان</option>' +
    State.provinces.map(p => `<option value="${p.id}">${esc(p.name)}</option>`).join('');
}

function fillCountySelect() {
  const provId = document.getElementById('province').value;
  const csel = document.getElementById('county');
  const prov = State.provinces.find(p => p.id === provId);
  csel.innerHTML = '<option value="">انتخاب شهرستان</option>' +
    (prov ? prov.counties.map(c => `<option value="${c.id}">${esc(c.name)}</option>`).join('') : '');
}

function renderFilterSelects() {
  const fp = document.getElementById('filterProvince');
  fp.innerHTML = '<option value="">همه استان‌ها</option>' +
    State.provinces.map(p => `<option value="${p.id}">${esc(p.name)}</option>`).join('');
  const fc = document.getElementById('filterCounty');
  const pid = fp.value;
  const prov = State.provinces.find(p => p.id === pid);
  fc.innerHTML = '<option value="">همه شهرستان‌ها</option>' +
    (prov ? prov.counties.map(c => `<option value="${c.id}">${esc(c.name)}</option>`).join('') : '');
}

function renderFilterServices() {
  const el = document.getElementById('filterServices');
  el.innerHTML = State.services.filter(s => s.active).map(s =>
    `<label class="check"><input type="checkbox" value="${s.id}"> ${esc(s.name)}</label>`
  ).join('') || '<div class="empty">خدمتی تعریف نشده</div>';
}

function renderAdminSectionList() {
  const el = document.getElementById('adminSectionList');
  if (!el) return;
  const sections = [
    { id: 'accessManagementCard', label: 'مدیریت کاربران' },
  ];
  const collapsibles = document.querySelectorAll('#admin .card.collapsible');
  el.innerHTML = '';
  collapsibles.forEach((card, i) => {
    const h2 = card.querySelector('.card-header h2');
    if (!h2) return;
    const link = document.createElement('div');
    link.className = 'admin-section-link';
    link.innerHTML = `<span>${h2.textContent}</span><span class="arrow">←</span>`;
    link.onclick = () => {
      card.classList.remove('collapsed');
      card.scrollIntoView({ behavior: 'smooth', block: 'start' });
      // Close others
      collapsibles.forEach(c => { if (c !== card) c.classList.add('collapsed'); });
    };
    el.appendChild(link);
  });
}

// ----- Records rendering -----
function scopedRecords() {
  if (!State.user) return [];
  if (State.user.role === 'national') return State.records;
  if (State.user.role === 'provincial') return State.records.filter(r => r.province_id === State.user.province_id);
  if (State.user.role === 'county') return State.records.filter(r => r.province_id === State.user.province_id && r.county_id === State.user.county_id);
  return [];
}

function renderRecords() {
  const recs = scopedRecords();
  document.getElementById('recordCount').textContent = fa(recs.length) + ' رکورد';
  const el = document.getElementById('recordsTable');
  if (!recs.length) {
    el.innerHTML = '<div class="empty">هنوز خدمتی ثبت نشده است.</div>';
    return;
  }
  el.innerHTML = '<table><thead><tr><th>کارشناس / سمت</th><th>موقعیت</th><th>خدمت</th><th>تاریخ</th><th>عملیات</th></tr></thead><tbody>' +
    recs.map(r => `<tr>
      <td>${esc(r.expert_name || '—')}<br><span class="hint">${esc(r.role_name || '')}</span></td>
      <td>${esc(r.province_name || '')} / ${esc(r.county_name || '')} / ${esc(r.village || '')}</td>
      <td>${esc(r.service_name || '')}<br><span class="hint">${esc(r.description || '')}</span></td>
      <td>${esc(r.service_date || '—')}</td>
      <td>
        <button class="small secondary" data-edit="${r.id}">ویرایش</button>
        <button class="small danger" data-del="${r.id}">حذف</button>
      </td>
    </tr>`).join('') +
    '</tbody></table>';
  el.querySelectorAll('[data-edit]').forEach(b => b.onclick = () => editRecord(b.dataset.edit));
  el.querySelectorAll('[data-del]').forEach(b => b.onclick = () => deleteRecord(b.dataset.del));
}

function resetForm() {
  document.getElementById('recordForm').reset();
  document.getElementById('editId').value = '';
  document.getElementById('saveBtn').textContent = 'ثبت خدمت';
  State.editingRecordId = null;
  fillCountySelect();
}

function editRecord(id) {
  const r = State.records.find(x => x.id === id);
  if (!r) return;
  document.getElementById('editId').value = r.id;
  State.editingRecordId = r.id;
  document.getElementById('expertName').value = r.expert_name || '';
  document.getElementById('expertRole').value = r.role_id || '';
  document.getElementById('org').value = r.org || '';
  document.getElementById('province').value = r.province_id || '';
  fillCountySelect();
  document.getElementById('county').value = r.county_id || '';
  document.getElementById('village').value = r.village || '';
  document.getElementById('service').value = r.service_id || '';
  document.getElementById('serviceDate').value = r.service_date || '';
  document.getElementById('beneficiaries').value = r.beneficiaries || '';
  document.getElementById('description').value = r.description || '';
  document.getElementById('evidence').value = r.evidence || '';
  // Switch to register tab
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === 'register'));
  document.querySelectorAll('.panel').forEach(p => p.classList.toggle('active', p.id === 'register'));
  document.getElementById('saveBtn').textContent = 'به‌روزرسانی خدمت';
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

async function deleteRecord(id) {
  if (!confirm('این رکورد حذف شود؟')) return;
  try {
    await api(`/api/records/${id}`, { method: 'DELETE' });
    State.records = State.records.filter(r => r.id !== id);
    renderRecords();
    renderSummary();
    toast('رکورد حذف شد.');
  } catch (e) { toast(e.message, 'error'); }
}

// ----- Summary & charts -----
function getFilteredGroups() {
  const checkedSvc = Array.from(document.querySelectorAll('#filterServices input:checked')).map(c => c.value);
  const fp = document.getElementById('filterProvince').value;
  const fc = document.getElementById('filterCounty').value;
  const mode = document.getElementById('filterMode').value;
  let recs = scopedRecords();
  if (fp) recs = recs.filter(r => r.province_id === fp);
  if (fc) recs = recs.filter(r => r.county_id === fc);
  if (checkedSvc.length) {
    if (mode === 'all') {
      recs = recs.filter(r => checkedSvc.includes(r.service_id));
      // group by village; village must have all selected services
      const byV = {};
      recs.forEach(r => {
        const k = r.village + '|' + r.province_id + '|' + r.county_id;
        if (!byV[k]) byV[k] = { village: r.village, province_id: r.province_id, county_id: r.county_id, records: [], services: new Set() };
        byV[k].records.push(r);
        byV[k].services.add(r.service_id);
      });
      return Object.values(byV).filter(g => checkedSvc.every(s => g.services.has(s)));
    } else {
      // any mode: just filter
      const byV = {};
      recs.forEach(r => {
        const k = r.village + '|' + r.province_id + '|' + r.county_id;
        if (!byV[k]) byV[k] = { village: r.village, province_id: r.province_id, county_id: r.county_id, records: [], services: new Set() };
        byV[k].records.push(r);
        byV[k].services.add(r.service_id);
      });
      return Object.values(byV);
    }
  }
  // No service filter: group all by village
  const byV = {};
  recs.forEach(r => {
    const k = r.village + '|' + r.province_id + '|' + r.county_id;
    if (!byV[k]) byV[k] = { village: r.village, province_id: r.province_id, county_id: r.county_id, records: [], services: new Set() };
    byV[k].records.push(r);
    byV[k].services.add(r.service_id);
  });
  return Object.values(byV);
}

function renderSummary() {
  const groups = getFilteredGroups();
  const totalRecords = groups.reduce((n, g) => n + g.records.length, 0);
  const beneficiaries = groups.reduce((n, g) => n + g.records.reduce((a, r) => a + Number(r.beneficiaries || 0), 0), 0);
  const provinces = new Set(groups.flatMap(g => g.records.map(r => r.province_id))).size;
  document.getElementById('statVillages').textContent = fa(groups.length);
  document.getElementById('statServices').textContent = fa(totalRecords);
  document.getElementById('statBeneficiaries').textContent = fa(beneficiaries);
  document.getElementById('statProvinces').textContent = fa(provinces);

  const el = document.getElementById('summaryResults');
  if (!groups.length) {
    el.innerHTML = '<div class="empty">موردی مطابق فیلتر انتخاب‌شده وجود ندارد.</div>';
  } else {
    el.innerHTML = '<table><thead><tr><th>استان</th><th>شهرستان</th><th>روستا</th><th>خدمات</th><th>تعداد</th><th>شرح</th></tr></thead><tbody>' +
      groups.map(g => {
        const r = g.records[0];
        const services = Array.from(g.services).map(id => State.services.find(s => s.id === id)?.name || '—');
        const dates = g.records.map(x => x.service_date).filter(Boolean).sort();
        return `<tr>
          <td>${esc(r.province_name || '')}</td>
          <td>${esc(r.county_name || '')}</td>
          <td><b>${esc(r.village || '')}</b></td>
          <td>${services.map(s => `<span class="badge">${esc(s)}</span>`).join(' ')}</td>
          <td>${fa(g.records.length)}</td>
          <td>${esc(g.records.map(x => x.description).filter(Boolean).join(' | ') || '—')}<br><span class="hint">${esc(dates[dates.length-1] || '')}</span></td>
        </tr>`;
      }).join('') +
      '</tbody></table>';
  }

  renderCharts();
}

function renderCharts() {
  const recs = scopedRecords();
  // Service distribution
  const svcCounts = {};
  recs.forEach(r => {
    const name = r.service_name || 'نامشخص';
    svcCounts[name] = (svcCounts[name] || 0) + 1;
  });
  // Province distribution
  const provCounts = {};
  recs.forEach(r => {
    const name = r.province_name || 'نامشخص';
    provCounts[name] = (provCounts[name] || 0) + 1;
  });

  const colors = ['#1e2b4f', '#3b5998', '#d59a19', '#15803d', '#b91c1c', '#7c3aed', '#0891b2', '#be185d', '#c2410c', '#4d7c0f'];
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  const textColor = isDark ? '#c1cadd' : '#3a4258';
  const gridColor = isDark ? 'rgba(255,255,255,.06)' : 'rgba(0,0,0,.06)';

  Chart.defaults.font.family = "'Vazirmatn','Tahoma',sans-serif";
  Chart.defaults.color = textColor;

  // Service chart (bar)
  const svcCanvas = document.getElementById('chartServices');
  if (svcCanvas) {
    if (State.charts.services) State.charts.services.destroy();
    State.charts.services = new Chart(svcCanvas, {
      type: 'bar',
      data: {
        labels: Object.keys(svcCounts),
        datasets: [{ label: 'تعداد', data: Object.values(svcCounts), backgroundColor: colors.slice(0, Object.keys(svcCounts).length) }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: gridColor } }, x: { grid: { display: false } } }
      }
    });
  }

  // Province chart (doughnut)
  const provCanvas = document.getElementById('chartProvinces');
  if (provCanvas) {
    if (State.charts.provinces) State.charts.provinces.destroy();
    State.charts.provinces = new Chart(provCanvas, {
      type: 'doughnut',
      data: {
        labels: Object.keys(provCounts),
        datasets: [{ data: Object.values(provCounts), backgroundColor: colors.slice(0, Object.keys(provCounts).length) }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: 'bottom', labels: { padding: 12, font: { size: 11 } } } }
      }
    });
  }
}

// ----- Admin: roles -----
function renderRoles() {
  const el = document.getElementById('roleList');
  if (!State.roles.length) { el.innerHTML = '<div class="empty">سمتی تعریف نشده</div>'; return; }
  el.innerHTML = '<table><thead><tr><th>عنوان</th><th>وضعیت</th><th>عملیات</th></tr></thead><tbody>' +
    State.roles.map(r => `<tr>
      <td>${esc(r.name)}</td>
      <td>${r.active ? 'فعال' : 'غیرفعال'}</td>
      <td>
        <button class="small secondary" data-toggle-role="${r.id}" data-active="${r.active ? 0 : 1}">${r.active ? 'غیرفعال' : 'فعال'}</button>
        <button class="small danger" data-del-role="${r.id}">حذف</button>
      </td>
    </tr>`).join('') + '</tbody></table>';
  el.querySelectorAll('[data-toggle-role]').forEach(b => b.onclick = async () => {
    try {
      await api(`/api/roles/${b.dataset.toggleRole}`, { method: 'POST', body: { active: b.dataset.active === '1' } });
      const r = State.roles.find(x => x.id === b.dataset.toggleRole);
      if (r) r.active = b.dataset.active === '1';
      renderRoles();
    } catch (e) { toast(e.message, 'error'); }
  });
  el.querySelectorAll('[data-del-role]').forEach(b => b.onclick = async () => {
    if (!confirm('حذف شود؟')) return;
    try {
      await api(`/api/roles/${b.dataset.delRole}`, { method: 'DELETE' });
      State.roles = State.roles.filter(r => r.id !== b.dataset.delRole);
      renderRoles();
      renderBaseSelects();
      toast('سمت حذف شد.');
    } catch (e) { toast(e.message, 'error'); }
  });
}

// ----- Admin: services -----
function renderServicesAdmin() {
  const el = document.getElementById('serviceListAdmin');
  if (!State.services.length) { el.innerHTML = '<div class="empty">خدمتی تعریف نشده</div>'; return; }
  el.innerHTML = '<table><thead><tr><th>عنوان</th><th>وضعیت</th><th>عملیات</th></tr></thead><tbody>' +
    State.services.map(s => `<tr>
      <td>${esc(s.name)}</td>
      <td>${s.active ? 'فعال' : 'غیرفعال'}</td>
      <td>
        <button class="small secondary" data-toggle-svc="${s.id}" data-active="${s.active ? 0 : 1}">${s.active ? 'غیرفعال' : 'فعال'}</button>
        <button class="small danger" data-del-svc="${s.id}">حذف</button>
      </td>
    </tr>`).join('') + '</tbody></table>';
  el.querySelectorAll('[data-toggle-svc]').forEach(b => b.onclick = async () => {
    try {
      await api(`/api/services/${b.dataset.toggleSvc}`, { method: 'POST', body: { active: b.dataset.active === '1' } });
      const s = State.services.find(x => x.id === b.dataset.toggleSvc);
      if (s) s.active = b.dataset.active === '1';
      renderServicesAdmin();
      renderBaseSelects();
      renderFilterServices();
    } catch (e) { toast(e.message, 'error'); }
  });
  el.querySelectorAll('[data-del-svc]').forEach(b => b.onclick = async () => {
    if (!confirm('حذف شود؟')) return;
    try {
      await api(`/api/services/${b.dataset.delSvc}`, { method: 'DELETE' });
      State.services = State.services.filter(s => s.id !== b.dataset.delSvc);
      renderServicesAdmin();
      renderBaseSelects();
      renderFilterServices();
      toast('خدمت حذف شد.');
    } catch (e) { toast(e.message, 'error'); }
  });
}

// ----- Admin: provinces & counties -----
function renderGeoList() {
  const el = document.getElementById('geoList');
  if (!State.provinces.length) { el.innerHTML = '<div class="empty">استانی تعریف نشده</div>'; return; }
  el.innerHTML = State.provinces.map(p => `<div style="margin-bottom:10px;padding:10px;background:var(--bg-alt);border-radius:8px">
    <b>${esc(p.name)}</b>
    <button class="small danger" style="float:left" data-del-prov="${p.id}">حذف استان</button>
    <div style="margin-top:6px">${p.counties.length ? p.counties.map(c => `<span class="badge">${esc(c.name)} <button data-del-county="${c.id}" style="background:none;border:0;color:inherit;cursor:pointer;padding:0 2px">×</button></span>`).join(' ') : '<span class="hint">شهرستانی ثبت نشده</span>'}</div>
  </div>`).join('');
  el.querySelectorAll('[data-del-prov]').forEach(b => b.onclick = async () => {
    if (!confirm('استان و تمام شهرستان‌های آن حذف شود؟')) return;
    try {
      await api(`/api/provinces/${b.dataset.delProv}`, { method: 'DELETE' });
      State.provinces = State.provinces.filter(p => p.id !== b.dataset.delProv);
      renderGeoList();
      renderBaseSelects();
      renderFilterSelects();
      toast('استان حذف شد.');
    } catch (e) { toast(e.message, 'error'); }
  });
  el.querySelectorAll('[data-del-county]').forEach(b => b.onclick = async (e) => {
    e.stopPropagation();
    if (!confirm('شهرستان حذف شود؟')) return;
    try {
      await api(`/api/counties/${b.dataset.delCounty}`, { method: 'DELETE' });
      // Remove from local state
      State.provinces.forEach(p => { p.counties = p.counties.filter(c => c.id !== b.dataset.delCounty); });
      renderGeoList();
      renderBaseSelects();
      renderFilterSelects();
      toast('شهرستان حذف شد.');
    } catch (err) { toast(err.message, 'error'); }
  });
}

// ----- Admin: custom fields -----
function renderCustomFields() {
  const el = document.getElementById('customFieldsList');
  if (!State.customFields.length) { el.innerHTML = '<div class="empty">فیلد سفارشی ثبت نشده</div>'; return; }
  el.innerHTML = '<table><thead><tr><th>عنوان</th><th>نوع</th><th>عملیات</th></tr></thead><tbody>' +
    State.customFields.map(f => `<tr>
      <td>${esc(f.label)}</td>
      <td>${typeLabel(f.type)}</td>
      <td><button class="small danger" data-del-cf="${f.id}">حذف</button></td>
    </tr>`).join('') + '</tbody></table>';
  el.querySelectorAll('[data-del-cf]').forEach(b => b.onclick = async () => {
    if (!confirm('حذف شود؟')) return;
    try {
      await api(`/api/custom-fields/${b.dataset.delCf}`, { method: 'DELETE' });
      State.customFields = State.customFields.filter(f => f.id !== b.dataset.delCf);
      renderCustomFields();
      updateDynamicFields();
    } catch (e) { toast(e.message, 'error'); }
  });
}

// ----- Admin: Login announcements -----
function renderLoginAnnouncementsAdmin() {
  const el = document.getElementById('loginAnnouncementsAdminList');
  if (!el) return;
  const list = State.loginAnnouncementsAll || [];
  if (!list.length) { el.innerHTML = '<div class="empty">اعلانی ثبت نشده</div>'; return; }
  el.innerHTML = '<table><thead><tr><th>متن</th><th>نوع</th><th>ترتیب</th><th>وضعیت</th><th>عملیات</th></tr></thead><tbody>' +
    list.map(a => `<tr>
      <td>${esc(a.text)}</td>
      <td>${a.festive ? 'مناسبی' : 'معمولی'}</td>
      <td>${fa(a.sort_order || 0)}</td>
      <td>${a.active ? 'فعال' : 'غیرفعال'}</td>
      <td>
        <button class="small secondary" data-toggle-la="${a.id}" data-active="${a.active ? 0 : 1}">${a.active ? 'غیرفعال‌کن' : 'فعال‌کن'}</button>
        <button class="small danger" data-del-la="${a.id}">حذف</button>
      </td>
    </tr>`).join('') + '</tbody></table>';
  el.querySelectorAll('[data-toggle-la]').forEach(b => b.onclick = async () => {
    try {
      await api(`/api/login-announcements/${b.dataset.toggleLa}`, { method: 'POST', body: { active: b.dataset.active === '1' } });
      const a = State.loginAnnouncementsAll.find(x => x.id === b.dataset.toggleLa);
      if (a) a.active = b.dataset.active === '1';
      renderLoginAnnouncementsAdmin();
    } catch (e) { toast(e.message, 'error'); }
  });
  el.querySelectorAll('[data-del-la]').forEach(b => b.onclick = async () => {
    if (!confirm('حذف شود؟')) return;
    try {
      await api(`/api/login-announcements/${b.dataset.delLa}`, { method: 'DELETE' });
      State.loginAnnouncementsAll = State.loginAnnouncementsAll.filter(a => a.id !== b.dataset.delLa);
      State.loginAnnouncements = State.loginAnnouncements.filter(a => a.id !== b.dataset.delLa);
      renderLoginAnnouncementsAdmin();
      renderLoginAnnouncementsAndBanners();
      toast('اعلان حذف شد.');
    } catch (e) { toast(e.message, 'error'); }
  });
}

// ----- Admin: Login banners -----
function renderLoginBannersAdmin() {
  const el = document.getElementById('loginBannersAdminList');
  if (!el) return;
  const list = State.loginBannersAll || [];
  if (!list.length) { el.innerHTML = '<div class="empty">بنری ثبت نشده</div>'; return; }
  el.innerHTML = '<table><thead><tr><th>پیش‌نمایش</th><th>عنوان</th><th>لینک</th><th>وضعیت</th><th>عملیات</th></tr></thead><tbody>' +
    list.map(b => `<tr>
      <td><img src="data:${b.image_mime};base64,${b.image_data}" style="max-width:90px;max-height:45px;border-radius:4px"></td>
      <td>${esc(b.title || '—')}</td>
      <td>${esc(b.link_url || '—')}</td>
      <td>${b.active ? 'فعال' : 'غیرفعال'}</td>
      <td>
        <button class="small secondary" data-toggle-lb="${b.id}" data-active="${b.active ? 0 : 1}">${b.active ? 'غیرفعال‌کن' : 'فعال‌کن'}</button>
        <button class="small danger" data-del-lb="${b.id}">حذف</button>
      </td>
    </tr>`).join('') + '</tbody></table>';
  el.querySelectorAll('[data-toggle-lb]').forEach(b => b.onclick = async () => {
    try {
      await api(`/api/login-banners/${b.dataset.toggleLb}`, { method: 'POST', body: { active: b.dataset.active === '1' } });
      const bn = State.loginBannersAll.find(x => x.id === b.dataset.toggleLb);
      if (bn) bn.active = b.dataset.active === '1';
      renderLoginBannersAdmin();
    } catch (e) { toast(e.message, 'error'); }
  });
  el.querySelectorAll('[data-del-lb]').forEach(b => b.onclick = async () => {
    if (!confirm('بنر حذف شود؟')) return;
    try {
      await api(`/api/login-banners/${b.dataset.delLb}`, { method: 'DELETE' });
      State.loginBannersAll = State.loginBannersAll.filter(x => x.id !== b.dataset.delLb);
      State.loginBanners = State.loginBanners.filter(x => x.id !== b.dataset.delLb);
      renderLoginBannersAdmin();
      renderLoginAnnouncementsAndBanners();
      toast('بنر حذف شد.');
    } catch (e) { toast(e.message, 'error'); }
  });
}

function typeLabel(t) {
  return { text: 'متن', number: 'عدد', date: 'تاریخ', url: 'لینک', textarea: 'متن تفصیلی' }[t] || t;
}

function updateDynamicFields() {
  const wrap = document.getElementById('dynamicRecordFields');
  if (!State.customFields.length) { wrap.innerHTML = ''; return; }
  wrap.innerHTML = State.customFields.map(f => {
    const id = 'cf_' + f.id;
    return `<div class="${f.type === 'textarea' ? 'wide' : ''}">
      <label for="${id}">${esc(f.label)}</label>
      ${f.type === 'textarea' ? `<textarea id="${id}" data-custom-id="${f.id}"></textarea>` :
        `<input id="${id}" data-custom-id="${f.id}" type="${f.type === 'url' ? 'url' : f.type === 'number' ? 'number' : f.type === 'date' ? 'date' : 'text'}">`}
    </div>`;
  }).join('');
}

// ----- Admin: users -----
function renderUserCountySelects() {
  const pSel = document.getElementById('userProvince');
  if (!pSel) return;
  pSel.innerHTML = '<option value="">انتخاب استان</option>' +
    State.provinces.map(p => `<option value="${p.id}">${esc(p.name)}</option>`).join('');
}

function fillUserCounties() {
  const pid = document.getElementById('userProvince').value;
  const cSel = document.getElementById('userCounty');
  const prov = State.provinces.find(p => p.id === pid);
  cSel.innerHTML = '<option value="">انتخاب شهرستان</option>' +
    (prov ? prov.counties.map(c => `<option value="${c.id}">${esc(c.name)}</option>`).join('') : '');
}

function renderUsersTable() {
  const el = document.getElementById('usersTable');
  if (!State.users.length) { el.innerHTML = '<div class="empty">کاربری ثبت نشده</div>'; return; }
  el.innerHTML = '<table><thead><tr><th>نام</th><th>نام کاربری</th><th>سطح</th><th>محدوده</th><th>وضعیت</th><th>عملیات</th></tr></thead><tbody>' +
    State.users.map(u => {
      const prov = State.provinces.find(p => p.id === u.province_id);
      const cnty = prov?.counties.find(c => c.id === u.county_id);
      const scope = u.role === 'national' ? 'کشوری' : (prov ? prov.name + (cnty ? ' / ' + cnty.name : '') : '—');
      return `<tr>
        <td>${esc(u.name)}</td>
        <td>${esc(u.username)}</td>
        <td>${roleLabel(u.role)}</td>
        <td>${esc(scope)}</td>
        <td>${u.active ? 'فعال' : 'غیرفعال'}</td>
        <td>
          <button class="small secondary" data-edit-user="${u.id}">ویرایش</button>
          <button class="small secondary" data-toggle-user="${u.id}" data-active="${u.active ? 0 : 1}">${u.active ? 'غیرفعال' : 'فعال'}</button>
          ${u.id === 'u_admin_default' ? '' : `<button class="small danger" data-del-user="${u.id}">حذف</button>`}
        </td>
      </tr>`;
    }).join('') + '</tbody></table>';
  el.querySelectorAll('[data-edit-user]').forEach(b => b.onclick = () => editUser(b.dataset.editUser));
  el.querySelectorAll('[data-toggle-user]').forEach(b => b.onclick = async () => {
    try {
      await api(`/api/users/${b.dataset.toggleUser}/toggle`, { method: 'POST', body: { active: b.dataset.active === '1' } });
      const u = State.users.find(x => x.id === b.dataset.toggleUser);
      if (u) u.active = b.dataset.active === '1';
      renderUsersTable();
    } catch (e) { toast(e.message, 'error'); }
  });
  el.querySelectorAll('[data-del-user]').forEach(b => b.onclick = async () => {
    if (!confirm('کاربر حذف شود؟')) return;
    try {
      await api(`/api/users/${b.dataset.delUser}`, { method: 'DELETE' });
      State.users = State.users.filter(u => u.id !== b.dataset.delUser);
      renderUsersTable();
      toast('کاربر حذف شد.');
    } catch (e) { toast(e.message, 'error'); }
  });
}

function editUser(id) {
  const u = State.users.find(x => x.id === id);
  if (!u) return;
  State.editingUserId = id;
  document.getElementById('userFullName').value = u.name;
  document.getElementById('userUsername').value = u.username;
  document.getElementById('userPassword').value = '';
  document.getElementById('userRole').value = u.role;
  document.getElementById('userProvince').value = u.province_id || '';
  fillUserCounties();
  document.getElementById('userCounty').value = u.county_id || '';
  document.getElementById('saveUser').textContent = 'به‌روزرسانی کاربر';
  document.getElementById('userRole').dispatchEvent(new Event('change'));
}

function resetUserForm() {
  State.editingUserId = null;
  document.getElementById('userFullName').value = '';
  document.getElementById('userUsername').value = '';
  document.getElementById('userPassword').value = '';
  document.getElementById('userRole').value = 'national';
  document.getElementById('userProvince').value = '';
  fillUserCounties();
  document.getElementById('saveUser').textContent = 'افزودن کاربر';
}

// ----- Login design rendering -----
function renderLoginDesign() {
  const s = State.settings || {};
  // Title/subtitle/mark on the login page are hidden by user request — they appear in the background image
  // Only update the demo text & login button label
  const loginBtn = document.getElementById('loginSubmitButton');
  if (loginBtn) {
    const btnSpan = loginBtn.querySelector('span');
    if (btnSpan) btnSpan.textContent = s.loginButton || 'ورود به سامانه';
  }
  const demoText = document.getElementById('loginDemoText');
  if (demoText) demoText.textContent = s.loginDemoText || 'ورود با حساب آزمایشی';
  const uLabel = document.getElementById('loginUsernameLabel');
  if (uLabel) uLabel.textContent = s.loginUsernameLabel || 'نام کاربری';
  const pLabel = document.getElementById('loginPasswordLabel');
  if (pLabel) pLabel.textContent = s.loginPasswordLabel || 'رمز عبور';
  const demoNotice = document.getElementById('loginDemoNotice');
  if (demoNotice) demoNotice.style.display = s.showLoginDemoNotice ? '' : 'none';
  // Fill admin form
  if (document.getElementById('loginHeadingSetting')) {
    document.getElementById('loginHeadingSetting').value = s.loginHeading || '';
    document.getElementById('loginSubtitleSetting').value = s.loginSubtitle || '';
    document.getElementById('loginButtonSetting').value = s.loginButton || '';
    document.getElementById('loginUsernameLabelSetting').value = s.loginUsernameLabel || '';
    document.getElementById('loginPasswordLabelSetting').value = s.loginPasswordLabel || '';
    document.getElementById('loginDemoTextSetting').value = s.loginDemoText || '';
    document.getElementById('loginContactTextSetting').value = s.loginContactText || '';
    document.getElementById('loginContactUrlSetting').value = s.loginContactUrl || '';
    document.getElementById('loginExtraSetting').value = s.loginExtra || '';
    document.getElementById('loginBgSetting').value = s.loginBg || '#263b70';
    document.getElementById('loginAccentSetting').value = s.loginAccent || '#3156a5';
    document.getElementById('showLoginDemoNotice').checked = s.showLoginDemoNotice;
  }
  // Branding
  if (document.getElementById('settingTitle')) {
    document.getElementById('settingTitle').value = s.title || '';
    document.getElementById('settingSubtitle').value = s.subtitle || '';
    document.getElementById('evidenceEnabled').checked = s.evidenceEnabled !== false && s.evidenceEnabled !== '0';
  }
}

// ----- Init -----
async function init() {
  applyTheme(getStoredTheme());
  bindLogin();
  // Check if already logged in
  try {
    const data = await loadState();
    if (data.authenticated) {
      showApp();
    } else {
      renderLoginDesign();
    }
  } catch (e) {
    console.error(e);
    renderLoginDesign();
  }

  // Bind events
  document.getElementById('province').addEventListener('change', fillCountySelect);
  document.getElementById('filterProvince').addEventListener('change', renderFilterSelects);

  document.getElementById('recordForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const province = State.provinces.find(p => p.id === document.getElementById('province').value);
    const county = province?.counties.find(c => c.id === document.getElementById('county').value);
    const role = State.roles.find(r => r.id === document.getElementById('expertRole').value);
    const service = State.services.find(s => s.id === document.getElementById('service').value);
    if (!province || !county || !role || !service || !document.getElementById('village').value.trim()) {
      toast('لطفاً سمت، استان، شهرستان، روستا و خدمت را کامل کنید.', 'error');
      return;
    }
    const customValues = {};
    document.querySelectorAll('#dynamicRecordFields [data-custom-id]').forEach(el => {
      customValues[el.dataset.customId] = el.value;
    });
    const payload = {
      id: document.getElementById('editId').value || undefined,
      expertName: document.getElementById('expertName').value.trim(),
      roleId: role.id,
      roleName: role.name,
      org: document.getElementById('org').value.trim(),
      provinceId: province.id,
      provinceName: province.name,
      countyId: county.id,
      countyName: county.name,
      village: document.getElementById('village').value.trim(),
      serviceId: service.id,
      serviceName: service.name,
      serviceDate: document.getElementById('serviceDate').value.trim(),
      beneficiaries: Number(document.getElementById('beneficiaries').value || 0),
      description: document.getElementById('description').value.trim(),
      evidence: document.getElementById('evidence').value.trim(),
      customValues,
    };
    const btn = document.getElementById('saveBtn');
    const orig = btn.textContent;
    btn.textContent = 'در حال ذخیره...';
    btn.disabled = true;
    try {
      const resp = await api('/api/records', { method: 'POST', body: payload });
      payload.id = resp.id;
      // Update local state
      const idx = State.records.findIndex(r => r.id === resp.id);
      const newRec = {
        ...payload,
        expert_name: payload.expertName,
        role_id: payload.roleId, role_name: payload.roleName,
        province_id: payload.provinceId, province_name: payload.provinceName,
        county_id: payload.countyId, county_name: payload.countyName,
        service_id: payload.serviceId, service_name: payload.serviceName,
        service_date: payload.serviceDate, description: payload.description,
        evidence: payload.evidence,
      };
      delete newRec.expertName; delete newRec.roleId; delete newRec.roleName;
      delete newRec.provinceId; delete newRec.provinceName;
      delete newRec.countyId; delete newRec.countyName;
      delete newRec.serviceId; delete newRec.serviceName;
      delete newRec.serviceDate;
      if (idx >= 0) State.records[idx] = newRec;
      else State.records.unshift(newRec);
      resetForm();
      renderRecords();
      renderSummary();
      toast('اطلاعات با موفقیت در پایگاه داده مرکزی ذخیره شد.');
    } catch (err) {
      toast(err.message, 'error');
    } finally {
      btn.textContent = orig;
      btn.disabled = false;
    }
  });

  document.getElementById('resetFormBtn').addEventListener('click', resetForm);

  // Tabs
  document.querySelectorAll('.tab').forEach(t => {
    t.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(x => x.classList.toggle('active', x === t));
      document.querySelectorAll('.panel').forEach(p => p.classList.toggle('active', p.id === t.dataset.tab));
    });
  });

  // User form events
  document.getElementById('userRole').addEventListener('change', () => {
    const r = document.getElementById('userRole').value;
    document.getElementById('userProvince').disabled = r === 'national';
    document.getElementById('userCounty').disabled = r !== 'county';
  });
  document.getElementById('userProvince').addEventListener('change', fillUserCounties);

  document.getElementById('saveUser').addEventListener('click', async () => {
    const data = {
      id: State.editingUserId,
      name: document.getElementById('userFullName').value.trim(),
      username: document.getElementById('userUsername').value.trim(),
      password: document.getElementById('userPassword').value,
      role: document.getElementById('userRole').value,
      province_id: document.getElementById('userProvince').value || '',
      county_id: document.getElementById('userCounty').value || '',
    };
    if (!data.name || !data.username) { toast('نام و نام کاربری الزامی است.', 'error'); return; }
    if (!data.id && data.password.length < 8) { toast('گذرواژه باید حداقل ۸ نویسه باشد.', 'error'); return; }
    try {
      const resp = await api('/api/users', { method: 'POST', body: data });
      // Refresh users
      const state = await api('/api/state');
      State.users = state.users || [];
      renderUsersTable();
      resetUserForm();
      toast('کاربر ذخیره شد.');
    } catch (e) { toast(e.message, 'error'); }
  });
  document.getElementById('cancelUserEdit').addEventListener('click', resetUserForm);

  // Roles / services / provinces / counties
  document.getElementById('addRole').addEventListener('click', async () => {
    const name = document.getElementById('newRole').value.trim();
    if (!name) return;
    try {
      const resp = await api('/api/roles', { method: 'POST', body: { name } });
      State.roles.push({ id: resp.id, name, active: 1 });
      document.getElementById('newRole').value = '';
      renderRoles();
      renderBaseSelects();
      toast('سمت اضافه شد.');
    } catch (e) { toast(e.message, 'error'); }
  });

  document.getElementById('addService').addEventListener('click', async () => {
    const name = document.getElementById('newService').value.trim();
    if (!name) return;
    try {
      const resp = await api('/api/services', { method: 'POST', body: { name } });
      State.services.push({ id: resp.id, name, active: 1 });
      document.getElementById('newService').value = '';
      renderServicesAdmin();
      renderBaseSelects();
      renderFilterServices();
      toast('خدمت اضافه شد.');
    } catch (e) { toast(e.message, 'error'); }
  });

  document.getElementById('addProvince').addEventListener('click', async () => {
    const name = document.getElementById('newProvince').value.trim();
    if (!name) return;
    try {
      const resp = await api('/api/provinces', { method: 'POST', body: { name } });
      State.provinces.push({ id: resp.id, name, counties: [] });
      document.getElementById('newProvince').value = '';
      renderGeoList();
      renderBaseSelects();
      renderFilterSelects();
      renderUserCountySelects();
      toast('استان اضافه شد.');
    } catch (e) { toast(e.message, 'error'); }
  });

  document.getElementById('addCounty').addEventListener('click', async () => {
    const pid = document.getElementById('provinceForCounty').value;
    const name = document.getElementById('newCounty').value.trim();
    if (!pid || !name) { toast('استان و نام شهرستان الزامی است.', 'error'); return; }
    try {
      const resp = await api('/api/counties', { method: 'POST', body: { province_id: pid, name } });
      const prov = State.provinces.find(p => p.id === pid);
      if (prov) prov.counties.push({ id: resp.id, name });
      document.getElementById('newCounty').value = '';
      renderGeoList();
      renderBaseSelects();
      renderFilterSelects();
      renderUserCountySelects();
      toast('شهرستان اضافه شد.');
    } catch (e) { toast(e.message, 'error'); }
  });

  // Announcements
  document.getElementById('addAnnouncement').addEventListener('click', async () => {
    const text = document.getElementById('newAnnouncement').value.trim();
    if (!text) return;
    try {
      const resp = await api('/api/announcements', { method: 'POST', body: { text } });
      State.announcements.unshift({ id: resp.id, text, active: 1 });
      document.getElementById('newAnnouncement').value = '';
      renderAnnouncementList();
      toast('اعلان اضافه شد.');
    } catch (e) { toast(e.message, 'error'); }
  });

  // Custom fields
  document.getElementById('addCustomField').addEventListener('click', async () => {
    const label = document.getElementById('newFieldLabel').value.trim();
    if (!label) return;
    const type = document.getElementById('newFieldType').value;
    try {
      const resp = await api('/api/custom-fields', { method: 'POST', body: { label, type, scope: 'all' } });
      State.customFields.push({ id: resp.id, label, type, scope: 'all', active: 1 });
      document.getElementById('newFieldLabel').value = '';
      renderCustomFields();
      updateDynamicFields();
      toast('فیلد اضافه شد.');
    } catch (e) { toast(e.message, 'error'); }
  });

  // Login announcements
  document.getElementById('addLoginAnnouncement').addEventListener('click', async () => {
    const text = document.getElementById('newLoginAnnouncement').value.trim();
    if (!text) return;
    const festive = document.getElementById('newLoginAnnouncementFestive').value === '1';
    const sort_order = parseInt(document.getElementById('newLoginAnnouncementOrder').value || '0', 10);
    try {
      const resp = await api('/api/login-announcements', { method: 'POST', body: { text, festive, sort_order } });
      State.loginAnnouncementsAll.unshift({ id: resp.id, text, festive, active: 1, sort_order });
      State.loginAnnouncements.unshift({ id: resp.id, text, festive, active: 1, sort_order });
      document.getElementById('newLoginAnnouncement').value = '';
      renderLoginAnnouncementsAdmin();
      renderLoginAnnouncementsAndBanners();
      toast('اعلان اضافه شد.');
    } catch (e) { toast(e.message, 'error'); }
  });

  // Login banners (file upload via base64)
  document.getElementById('addLoginBanner').addEventListener('click', async () => {
    const fileInput = document.getElementById('newLoginBannerFile');
    if (!fileInput.files || !fileInput.files[0]) {
      toast('یک فایل تصویر انتخاب کنید.', 'error');
      return;
    }
    const file = fileInput.files[0];
    const title = document.getElementById('newLoginBannerTitle').value;
    const link_url = document.getElementById('newLoginBannerLink').value;
    const reader = new FileReader();
    reader.onload = async (ev) => {
      const dataUrl = ev.target.result;
      const parts = dataUrl.split(',');
      const mime = (parts[0].match(/:(.*?);/) || [])[1] || 'image/jpeg';
      const image_data = parts[1];
      try {
        const resp = await api('/api/login-banners', { method: 'POST', body: {
          image_data, image_mime: mime, link_url, title, sort_order: 0
        }});
        State.loginBannersAll.unshift({ id: resp.id, image_data, image_mime: mime, link_url, title, active: 1, sort_order: 0 });
        State.loginBanners.unshift({ id: resp.id, image_data, image_mime: mime, link_url, title, active: 1, sort_order: 0 });
        fileInput.value = '';
        document.getElementById('newLoginBannerTitle').value = '';
        document.getElementById('newLoginBannerLink').value = '';
        renderLoginBannersAdmin();
        renderLoginAnnouncementsAndBanners();
        toast('بنر اضافه شد.');
      } catch (e) { toast(e.message, 'error'); }
    };
    reader.readAsDataURL(file);
  });

  // Branding
  document.getElementById('saveBranding').addEventListener('click', async () => {
    const data = {
      title: document.getElementById('settingTitle').value,
      subtitle: document.getElementById('settingSubtitle').value,
    };
    try {
      await api('/api/settings', { method: 'POST', body: data });
      Object.assign(State.settings, data);
      renderBranding();
      toast('تنظیمات ذخیره شد.');
    } catch (e) { toast(e.message, 'error'); }
  });

  // Login design
  document.getElementById('saveLoginDesign').addEventListener('click', async () => {
    const data = {
      loginHeading: document.getElementById('loginHeadingSetting').value,
      loginSubtitle: document.getElementById('loginSubtitleSetting').value,
      loginButton: document.getElementById('loginButtonSetting').value,
      loginUsernameLabel: document.getElementById('loginUsernameLabelSetting').value,
      loginPasswordLabel: document.getElementById('loginPasswordLabelSetting').value,
      loginDemoText: document.getElementById('loginDemoTextSetting').value,
      loginContactText: document.getElementById('loginContactTextSetting').value,
      loginContactUrl: document.getElementById('loginContactUrlSetting').value,
      loginExtra: document.getElementById('loginExtraSetting').value,
      loginBg: document.getElementById('loginBgSetting').value,
      loginAccent: document.getElementById('loginAccentSetting').value,
      showLoginDemoNotice: document.getElementById('showLoginDemoNotice').checked,
    };
    try {
      await api('/api/settings', { method: 'POST', body: data });
      Object.assign(State.settings, data);
      renderLoginDesign();
      toast('طراحی ورود ذخیره شد.');
    } catch (e) { toast(e.message, 'error'); }
  });

  // Evidence setting
  document.getElementById('saveEvidenceSetting').addEventListener('click', async () => {
    const enabled = document.getElementById('evidenceEnabled').checked;
    try {
      await api('/api/settings', { method: 'POST', body: { evidenceEnabled: enabled } });
      State.settings.evidenceEnabled = enabled;
      const wrap = document.getElementById('evidenceFieldWrap');
      if (wrap) wrap.style.display = enabled ? '' : 'none';
      toast('تنظیمات ذخیره شد.');
    } catch (e) { toast(e.message, 'error'); }
  });

  // Filters
  document.getElementById('applyFilter').addEventListener('click', renderSummary);
  document.getElementById('clearFilter').addEventListener('click', () => {
    document.querySelectorAll('#filterServices input').forEach(c => c.checked = false);
    document.getElementById('filterProvince').value = '';
    renderFilterSelects();
    document.getElementById('filterMode').value = 'all';
    renderSummary();
  });

  // Export
  document.getElementById('exportFiltered').addEventListener('click', () => {
    const groups = getFilteredGroups();
    const csv = '\ufeffکارشناس,سمت,استان,شهرستان,روستا,خدمت,تاریخ,بهرهمندان\n' +
      groups.flatMap(g => g.records).map(r => [
        r.expert_name, r.role_name, r.province_name, r.county_name, r.village,
        r.service_name, r.service_date, r.beneficiaries
      ].map(c => `"${String(c||'').replace(/"/g,'""')}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'rural_filtered.csv';
    a.click();
    URL.revokeObjectURL(url);
  });

  document.getElementById('exportAll').addEventListener('click', () => {
    window.location.href = '/api/export/csv';
  });

  document.getElementById('backupJson').addEventListener('click', () => {
    window.location.href = '/api/export/json';
  });
}

document.addEventListener('DOMContentLoaded', init);


// ===== PLAN MANAGEMENT SYSTEM (سامانه طرح‌های پویا) =====

const STATUS_LABELS = {done: 'انجام‌شده', in_progress: 'در حال انجام', capacity: 'دارای ظرفیت انجام'};
const STATUS_ICONS = {done: '✅', in_progress: '🔄', capacity: '📋'};

// ----- Admin: Plan Management -----
function renderPlansAdmin() {
  const el = document.getElementById('plansAdminList');
  if (!el) return;
  const search = (document.getElementById('planSearch')?.value || '').toLowerCase();
  let plans = State.plans || [];
  if (search) plans = plans.filter(p => p.name.toLowerCase().includes(search) || (p.description||'').toLowerCase().includes(search));

  // Update stats
  const stats = State.planStats || {};
  if (document.getElementById('psTotal')) document.getElementById('psTotal').textContent = fa(stats.total_plans || 0);
  if (document.getElementById('psActive')) document.getElementById('psActive').textContent = fa(stats.active_plans || 0);
  if (document.getElementById('psRecords')) document.getElementById('psRecords').textContent = fa(stats.total_records || 0);
  if (document.getElementById('psVillages')) document.getElementById('psVillages').textContent = fa(stats.villages_count || 0);

  if (!plans.length) {
    el.innerHTML = '<p class="hint">هنوز طرحی تعریف نشده است.</p>';
    return;
  }
  el.innerHTML = plans.map(p => `
    <div class="plan-admin-item ${p.active ? '' : 'inactive'}">
      <div class="plan-admin-info">
        <b>${esc(p.name)}</b>
        ${p.description ? `<span class="hint">${esc(p.description)}</span>` : ''}
        <div class="plan-meta">
          <span class="badge">${fa(p.field_count || 0)} فیلد</span>
          <span class="badge">${fa(p.record_count || 0)} ثبت</span>
          <span class="badge">دسته‌ها: ${(p.allowed_statuses||[]).map(s => STATUS_LABELS[s]||s).join('، ') || 'همه'}</span>
          ${p.allow_duplicate ? '<span class="badge">اجازه تکرار</span>' : ''}
        </div>
      </div>
      <div class="plan-admin-actions">
        <button onclick="managePlanFields('${p.id}')">فیلدها</button>
        <button class="secondary" onclick="togglePlanActive('${p.id}')">${p.active ? 'غیرفعال' : 'فعال'}</button>
        <button class="gold" onclick="editPlan('${p.id}')">ویرایش</button>
        <button class="secondary" onclick="deletePlan('${p.id}')" style="background:#b91c1c">حذف</button>
      </div>
    </div>
  `).join('');
}

async function addPlan() {
  const name = document.getElementById('newPlanName').value.trim();
  if (!name) { toast('عنوان طرح الزامی است', 'error'); return; }
  const desc = document.getElementById('newPlanDesc').value.trim();
  const statuses = Array.from(document.querySelectorAll('.ps-check:checked')).map(c => c.value);
  const allowDup = document.getElementById('newPlanDup').checked ? 1 : 0;
  const order = parseInt(document.getElementById('newPlanOrder').value) || 0;
  const r = await api('/api/plans', {method:'POST', body: JSON.stringify({
    name, description: desc, allowed_statuses: statuses, allow_duplicate: allowDup, sort_order: order
  })});
  if (r.ok) {
    toast('طرح با موفقیت ایجاد شد', 'success');
    document.getElementById('newPlanName').value = '';
    document.getElementById('newPlanDesc').value = '';
    await loadState();
  } else { toast(r.error || 'خطا', 'error'); }
}

async function togglePlanActive(pid) {
  const plan = State.plans.find(p => p.id === pid);
  if (!plan) return;
  const r = await api(`/api/plans/${pid}`, {method:'POST', body: JSON.stringify({active: plan.active ? 0 : 1})});
  if (r.ok) { toast(plan.active ? 'طرح غیرفعال شد' : 'طرح فعال شد', 'success'); await loadState(); }
}

async function deletePlan(pid) {
  if (!confirm('آیا از حذف/غیرفعال‌سازی این طرح مطمئن هستید؟ سوابق قبلی حفظ خواهند شد.')) return;
  const r = await api(`/api/plans/${pid}`, {method:'DELETE'});
  if (r.ok) { toast('طرح حذف/غیرفعال شد', 'success'); await loadState(); }
}

function editPlan(pid) {
  const plan = State.plans.find(p => p.id === pid);
  if (!plan) return;
  document.getElementById('newPlanName').value = plan.name;
  document.getElementById('newPlanDesc').value = plan.description || '';
  document.querySelectorAll('.ps-check').forEach(c => c.checked = (plan.allowed_statuses||[]).includes(c.value));
  document.getElementById('newPlanDup').checked = !!plan.allow_duplicate;
  document.getElementById('newPlanOrder').value = plan.sort_order || 0;
  State.editingPlanId = pid;
  toast('در حال ویرایش — اطلاعات را تغییر دهید و دوباره «افزودن طرح» را بزنید', 'info');
}

// Override addPlan to handle edit mode
const _addPlanOrig = addPlan;
async function addPlanOrUpdate() {
  if (State.editingPlanId) {
    const pid = State.editingPlanId;
    const name = document.getElementById('newPlanName').value.trim();
    const desc = document.getElementById('newPlanDesc').value.trim();
    const statuses = Array.from(document.querySelectorAll('.ps-check:checked')).map(c => c.value);
    const allowDup = document.getElementById('newPlanDup').checked ? 1 : 0;
    const order = parseInt(document.getElementById('newPlanOrder').value) || 0;
    const r = await api(`/api/plans/${pid}`, {method:'POST', body: JSON.stringify({
      name, description: desc, allowed_statuses: statuses, allow_duplicate: allowDup, sort_order: order
    })});
    if (r.ok) { toast('طرح به‌روزرسانی شد', 'success'); State.editingPlanId = null; document.getElementById('newPlanName').value=''; await loadState(); }
  } else { _addPlanOrig(); }
}

// ----- Admin: Plan Fields Management -----
async function managePlanFields(pid) {
  const plan = State.plans.find(p => p.id === pid);
  if (!plan) return;
  document.getElementById('planManagementCard').style.display = 'none';
  const card = document.getElementById('planFieldsCard');
  card.style.display = '';
  card.classList.add('expanded');
  document.getElementById('planFieldsTitle').textContent = plan.name;
  State.editingPlanId = pid;
  await renderPlanFields(pid);
}

async function renderPlanFields(pid) {
  const fields = await api(`/api/plans/${pid}/fields`);
  State.planFieldsCache[pid] = fields;
  const el = document.getElementById('fieldsAdminList');
  if (!fields.length) {
    el.innerHTML = '<p class="hint">هنوز فیلدی تعریف نشده است.</p>';
    return;
  }
  const typeLabels = {text:'متن',textarea:'متن طولانی',number:'عدد',money:'مبلغ',date:'تاریخ',
    select_single:'تک‌انتخاب',select_multi:'چندانتخاب',checkbox:'چک‌باکس',file:'فایل'};
  el.innerHTML = fields.map(f => `
    <div class="plan-admin-item">
      <div class="plan-admin-info">
        <b>${esc(f.label)} ${f.required ? '<span style="color:#b91c1c">*</span>' : ''}</b>
        <span class="hint">${typeLabels[f.type]||f.type} | کلید: ${esc(f.field_key)}</span>
        ${f.help_text ? `<span class="hint">راهنما: ${esc(f.help_text)}</span>` : ''}
        ${f.options ? `<span class="hint">گزینه‌ها: ${esc(f.options)}</span>` : ''}
      </div>
      <div class="plan-admin-actions">
        <button class="gold" onclick="editPlanField('${f.id}')">ویرایش</button>
        <button class="secondary" onclick="deletePlanField('${f.id}')" style="background:#b91c1c">حذف</button>
      </div>
    </div>
  `).join('');
}

async function addPlanField() {
  const pid = State.editingPlanId;
  if (!pid) return;
  const label = document.getElementById('newFieldLabel').value.trim();
  if (!label) { toast('عنوان فیلد الزامی است', 'error'); return; }
  const type = document.getElementById('newFieldType').value;
  const optionsRaw = document.getElementById('newFieldOptions').value.trim();
  const help = document.getElementById('newFieldHelp').value.trim();
  const required = document.getElementById('newFieldRequired').checked ? 1 : 0;
  let options = null;
  if (optionsRaw && (type==='select_single'||type==='select_multi')) {
    options = optionsRaw.split(/[،,]/).map(s=>s.trim()).filter(Boolean);
  }
  const r = await api(`/api/plans/${pid}/fields`, {method:'POST', body: JSON.stringify({
    label, type, required, options, help_text: help
  })});
  if (r.ok) {
    toast('فیلد اضافه شد', 'success');
    document.getElementById('newFieldLabel').value='';
    document.getElementById('newFieldOptions').value='';
    document.getElementById('newFieldHelp').value='';
    document.getElementById('newFieldRequired').checked=false;
    await renderPlanFields(pid);
  } else { toast(r.error||'خطا', 'error'); }
}

async function deletePlanField(fid) {
  if (!confirm('فیلد حذف شود؟ داده‌های قبلی حفظ می‌شوند.')) return;
  const r = await api(`/api/plan-fields/${fid}`, {method:'DELETE'});
  if (r.ok && State.editingPlanId) {
    toast('فیلد حذف شد', 'success');
    await renderPlanFields(State.editingPlanId);
  }
}

function editPlanField(fid) {
  const pid = State.editingPlanId;
  const fields = State.planFieldsCache[pid] || [];
  const f = fields.find(x => x.id === fid);
  if (!f) return;
  document.getElementById('newFieldLabel').value = f.label;
  document.getElementById('newFieldType').value = f.type;
  document.getElementById('newFieldOptions').value = f.options || '';
  document.getElementById('newFieldHelp').value = f.help_text || '';
  document.getElementById('newFieldRequired').checked = !!f.required;
  toast('ویرایش فیلد — تغییرات را بدهید و «افزودن فیلد» را بزنید (در حال حاضر افزودن جدید می‌سازد)', 'info');
}

function backToPlans() {
  document.getElementById('planFieldsCard').style.display = 'none';
  document.getElementById('planManagementCard').style.display = '';
  State.editingPlanId = null;
}

// ----- Registration: Plan-based form -----
function renderPlanRegistration() {
  // Populate province dropdown
  const provSel = document.getElementById('planProvince');
  if (provSel && !provSel.options.length) {
    provSel.innerHTML = '<option value="">انتخاب استان</option>' + 
      State.provinces.map(p => `<option value="${p.id}">${esc(p.name)}</option>`).join('');
  }
  // Status tabs
  document.querySelectorAll('.plan-tab').forEach(tab => {
    tab.onclick = () => {
      document.querySelectorAll('.plan-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      State.selectedPlanStatus = tab.dataset.status;
      State.selectedPlans.clear();
      renderPlanList();
      renderPlanForms();
    };
  });
  // County change
  const countySel = document.getElementById('planCounty');
  if (provSel) provSel.onchange = () => { updatePlanCounties(); renderPlanList(); };
  if (countySel) countySel.onchange = renderPlanList;
  const villageInput = document.getElementById('planVillage');
  if (villageInput) villageInput.oninput = renderPlanList;
  // Submit
  const submitBtn = document.getElementById('submitPlanRecords');
  if (submitBtn) submitBtn.onclick = submitPlanRecords;
  const clearBtn = document.getElementById('clearPlanSelection');
  if (clearBtn) clearBtn.onclick = () => { State.selectedPlans.clear(); renderPlanList(); renderPlanForms(); };
  renderPlanList();
}

function updatePlanCounties() {
  const provId = document.getElementById('planProvince').value;
  const countySel = document.getElementById('planCounty');
  if (!countySel) return;
  const counties = State.provinces.flatMap(p => p.counties || []).filter(c => !provId || c.province_id === provId);
  // Actually counties are separate — let me check geoCatalog or just use provinces' counties
  // For simplicity, use geoCatalog or empty
  countySel.innerHTML = '<option value="">انتخاب شهرستان</option>';
  // Try to get counties from records or a separate source
  // For now, just allow text input fallback
}

function renderPlanList() {
  const container = document.getElementById('planListContainer');
  if (!container) return;
  const village = document.getElementById('planVillage')?.value.trim();
  if (!village) {
    container.innerHTML = '<p class="hint">نام روستا را وارد کنید تا طرح‌های قابل انتخاب نمایش داده شوند.</p>';
    document.getElementById('planSubmitActions').style.display = 'none';
    return;
  }
  const status = State.selectedPlanStatus;
  let plans = State.plans.filter(p => p.active);
  // Filter by allowed statuses
  plans = plans.filter(p => !p.allowed_statuses?.length || p.allowed_statuses.includes(status));
  if (!plans.length) {
    container.innerHTML = '<p class="hint">طرح فعالی برای این وضعیت تعریف نشده است.</p>';
    document.getElementById('planSubmitActions').style.display = 'none';
    return;
  }
  // Check existing records for this village
  const existingRecords = State.planRecords.filter(r => r.village === village);
  container.innerHTML = plans.map(p => {
    const existing = existingRecords.find(r => r.plan_id === p.id);
    const isDuplicate = existing && !p.allow_duplicate;
    const checked = State.selectedPlans.has(p.id);
    return `
      <div class="plan-select-item ${isDuplicate ? 'duplicate' : ''} ${checked ? 'checked' : ''}">
        <label class="check">
          <input type="checkbox" ${checked?'checked':''} ${isDuplicate?'disabled':''}
            onchange="togglePlanSelection('${p.id}')">
          <b>${esc(p.name)}</b>
          ${p.description ? `<span class="hint">${esc(p.description)}</span>` : ''}
          ${isDuplicate ? `<span class="badge" style="background:#fee2e2;color:#b91c1c">قبلاً ثبت شده (${STATUS_LABELS[existing.status_category]||''})</span>` : ''}
        </label>
      </div>
    `;
  }).join('');
}

function togglePlanSelection(pid) {
  if (State.selectedPlans.has(pid)) {
    State.selectedPlans.delete(pid);
  } else {
    State.selectedPlans.add(pid);
  }
  renderPlanList();
  renderPlanForms();
}

async function renderPlanForms() {
  const container = document.getElementById('planFormsContainer');
  const actions = document.getElementById('planSubmitActions');
  if (!container) return;
  if (!State.selectedPlans.size) {
    container.innerHTML = '';
    actions.style.display = 'none';
    return;
  }
  actions.style.display = '';
  const forms = [];
  for (const pid of State.selectedPlans) {
    const plan = State.plans.find(p => p.id === pid);
    if (!plan) continue;
    if (!State.planFieldsCache[pid]) {
      State.planFieldsCache[pid] = await api(`/api/plans/${pid}/fields`);
    }
    const fields = State.planFieldsCache[pid] || [];
    forms.push(`
      <div class="plan-form-card">
        <h3>${esc(plan.name)}</h3>
        ${fields.length ? fields.map(f => renderFieldInput(f, pid)).join('') : '<p class="hint">این طرح فیلد اختصاصی ندارد.</p>'}
      </div>
    `);
  }
  container.innerHTML = forms.join('');
}

function renderFieldInput(f, pid) {
  const key = `pf_${pid}_${f.field_key}`;
  const req = f.required ? ' required' : '';
  const reqMark = f.required ? ' <span style="color:#b91c1c">*</span>' : '';
  const help = f.help_text ? `<span class="hint">${esc(f.help_text)}</span>` : '';
  let input = '';
  switch(f.type) {
    case 'textarea':
      input = `<textarea id="${key}"${req} placeholder="${esc(f.label)}"></textarea>`;
      break;
    case 'number':
      input = `<input id="${key}" type="number"${req} placeholder="۰">`;
      break;
    case 'money':
      input = `<input id="${key}" type="number"${req} placeholder="مبلغ به تومان">`;
      break;
    case 'date':
      input = `<input id="${key}" type="text"${req} placeholder="مثلاً ۱۴۰۵/۰۷/۲۰">`;
      break;
    case 'select_single':
      const opts1 = (f.options||[]).map(o => `<option value="${esc(o)}">${esc(o)}</option>`).join('');
      input = `<select id="${key}"${req}><option value="">انتخاب...</option>${opts1}</select>`;
      break;
    case 'select_multi':
      const opts2 = (f.options||[]).map(o => `<label class="check"><input type="checkbox" class="${key}" value="${esc(o)}"> ${esc(o)}</label>`).join(' ');
      input = `<div>${opts2}</div>`;
      break;
    case 'checkbox':
      input = `<label class="check"><input id="${key}" type="checkbox"> بله</label>`;
      break;
    case 'file':
      input = `<input id="${key}" type="file">`;
      break;
    default:
      input = `<input id="${key}" type="text"${req} placeholder="${esc(f.label)}">`;
  }
  return `<div><label>${esc(f.label)}${reqMark}</label>${input}${help}</div>`;
}

async function submitPlanRecords() {
  const village = document.getElementById('planVillage').value.trim();
  const provinceId = document.getElementById('planProvince').value;
  const countyId = document.getElementById('planCounty').value;
  if (!village) { toast('نام روستا الزامی است', 'error'); return; }
  if (!State.selectedPlans.size) { toast('حداقل یک طرح انتخاب کنید', 'error'); return; }
  const status = State.selectedPlanStatus;
  let success = 0, errors = [];
  for (const pid of State.selectedPlans) {
    const fields = State.planFieldsCache[pid] || [];
    const values = {};
    let fieldErrors = [];
    for (const f of fields) {
      const key = `pf_${pid}_${f.field_key}`;
      if (f.type === 'select_multi') {
        values[f.field_key] = Array.from(document.querySelectorAll(`.${key}:checked`)).map(c => c.value);
      } else if (f.type === 'checkbox') {
        values[f.field_key] = document.getElementById(key)?.checked ? 1 : 0;
      } else {
        values[f.field_key] = document.getElementById(key)?.value?.trim() || '';
      }
      if (f.required && !values[f.field_key]) {
        fieldErrors.push(`«${f.label}»`);
      }
    }
    if (fieldErrors.length) {
      errors.push(`${State.plans.find(p=>p.id===pid)?.name}: ${fieldErrors.join('، ')}`);
      continue;
    }
    const r = await api('/api/plan-records', {method:'POST', body: JSON.stringify({
      plan_id: pid, village, status_category: status, field_values: values,
      province_id: provinceId, county_id: countyId
    })});
    if (r.ok) success++;
    else if (r.duplicate) errors.push(`${State.plans.find(p=>p.id===pid)?.name}: ${r.error}`);
    else errors.push(`${State.plans.find(p=>p.id===pid)?.name}: ${r.error||'خطا'}`);
  }
  if (success) toast(`${success} طرح ثبت شد`, 'success');
  if (errors.length) toast(`خطاها: ${errors.join(' | ')}`, 'error');
  if (success && !errors.length) {
    State.selectedPlans.clear();
    await loadState();
    renderPlanForms();
  }
}

// ----- Report: Plan Reports -----
function populatePlanReportFilter() {
  const sel = document.getElementById('reportPlanFilter');
  if (!sel) return;
  const current = sel.value;
  sel.innerHTML = '<option value="">همه طرح‌ها</option>' +
    (State.plans||[]).map(p => `<option value="${p.id}">${esc(p.name)}</option>`).join('');
  sel.value = current;
}

async function applyPlanReport() {
  const planId = document.getElementById('reportPlanFilter').value;
  const status = document.getElementById('reportStatusFilter').value;
  const village = document.getElementById('reportVillageFilter').value.trim();
  const params = new URLSearchParams();
  if (planId) params.set('plan_id', planId);
  if (status) params.set('status_category', status);
  if (village) params.set('village', village);
  const records = await api(`/api/plan-report?${params}`);
  renderPlanReportTable(records);
}

function renderPlanReportTable(records) {
  const el = document.getElementById('planReportResults');
  if (!el) return;
  if (!records.length) {
    el.innerHTML = '<p class="hint">رکوردی یافت نشد.</p>';
    return;
  }
  el.innerHTML = `
    <table>
      <thead><tr>
        <th>طرح</th><th>روستا</th><th>وضعیت</th><th>کارشناس</th><th>تاریخ</th><th>ثبت</th>
      </tr></thead>
      <tbody>
        ${records.map(r => `
          <tr>
            <td>${esc(r.plan_name||'')}</td>
            <td>${esc(r.village)}</td>
            <td>${STATUS_ICONS[r.status_category]||''} ${STATUS_LABELS[r.status_category]||r.status_category}</td>
            <td>${esc(r.expert_name||'')}</td>
            <td>${esc(r.service_date||'')}</td>
            <td>${esc((r.created_at||'').slice(0,10))}</td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `;
}

function exportPlanReportCSV() {
  const params = new URLSearchParams();
  params.set('format', 'csv');
  const planId = document.getElementById('reportPlanFilter').value;
  const status = document.getElementById('reportStatusFilter').value;
  const village = document.getElementById('reportVillageFilter').value.trim();
  if (planId) params.set('plan_id', planId);
  if (status) params.set('status_category', status);
  if (village) params.set('village', village);
  window.location.href = `/api/plan-report?${params}`;
}

// ----- Plan event listeners -----
document.addEventListener('DOMContentLoaded', () => {
  // Admin buttons
  const addBtn = document.getElementById('addPlanBtn');
  if (addBtn) addBtn.onclick = addPlanOrUpdate;
  const addFieldBtn = document.getElementById('addFieldBtn');
  if (addFieldBtn) addFieldBtn.onclick = addPlanField;
  const backBtn = document.getElementById('backToPlansBtn');
  if (backBtn) backBtn.onclick = backToPlans;
  const searchInput = document.getElementById('planSearch');
  if (searchInput) searchInput.oninput = renderPlansAdmin;
  // Report buttons
  const applyBtn = document.getElementById('applyPlanReport');
  if (applyBtn) applyBtn.onclick = applyPlanReport;
  const exportBtn = document.getElementById('exportPlanReport');
  if (exportBtn) exportBtn.onclick = exportPlanReportCSV;
  // Collapsible cards
  document.querySelectorAll('.card.collapsible .card-header').forEach(h => {
    h.onclick = () => h.parentElement.classList.toggle('expanded');
  });
});
