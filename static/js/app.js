/* Rural Services System - Modern Stylesheet */
/* Font: Vazirmatn from CDN */
@import url('https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@v33.003/Vazirmatn-font-face.css');

:root {
  --navy: #1e2b4f;
  --navy-light: #2d3f6e;
  --blue: #3b5998;
  --gold: #d59a19;
  --gold-light: #f0b040;
  --bg: #f4f6fa;
  --bg-alt: #eef1f7;
  --ink: #1e2637;
  --ink-soft: #3a4258;
  --muted: #6b7280;
  --line: #dfe4ee;
  --line-soft: #e9edf5;
  --white: #ffffff;
  --green: #15803d;
  --green-bg: #dcfce7;
  --red: #b91c1c;
  --red-bg: #fee2e2;
  --shadow-sm: 0 1px 2px rgba(30,43,79,.04), 0 1px 3px rgba(30,43,79,.06);
  --shadow-md: 0 4px 12px rgba(30,43,79,.08), 0 2px 4px rgba(30,43,79,.04);
  --shadow-lg: 0 12px 32px rgba(30,43,79,.12), 0 4px 12px rgba(30,43,79,.06);
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 16px;
  --radius-xl: 22px;
  --font: 'Vazirmatn', 'Tahoma', 'Segoe UI', system-ui, -apple-system, sans-serif;
}

/* Dark theme */
html[data-theme="dark"] {
  --navy: #c5d0f0;
  --navy-light: #a9b8e0;
  --blue: #8eaaf5;
  --bg: #0f1729;
  --bg-alt: #18223a;
  --ink: #e6ebf5;
  --ink-soft: #c1cadd;
  --muted: #8b94ac;
  --line: #2a3654;
  --line-soft: #212c47;
  --white: #1a253c;
  --green-bg: #0d3322;
  --red-bg: #3b1717;
  --shadow-sm: 0 1px 2px rgba(0,0,0,.3);
  --shadow-md: 0 4px 12px rgba(0,0,0,.4);
  --shadow-lg: 0 12px 32px rgba(0,0,0,.5);
}

* { box-sizing: border-box; }

body {
  margin: 0;
  background: var(--bg);
  font-family: var(--font);
  color: var(--ink);
  line-height: 1.75;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  transition: background .25s ease, color .25s ease;
}

/* ===== HEADER ===== */
header {
  background: linear-gradient(135deg, var(--navy) 0%, var(--blue) 100%);
  color: white;
  padding: 22px max(18px, calc((100% - 1180px)/2));
  box-shadow: var(--shadow-md);
  position: relative;
  overflow: hidden;
}

html[data-theme="dark"] header {
  background: linear-gradient(135deg, #131c3a 0%, #1f2a52 100%);
}

header::before {
  content: '';
  position: absolute;
  top: -50%; left: -10%;
  width: 60%; height: 200%;
  background: radial-gradient(ellipse at center, rgba(255,255,255,.08), transparent 70%);
  pointer-events: none;
}

header h1 {
  margin: 0;
  font-size: clamp(20px, 3vw, 28px);
  font-weight: 700;
  letter-spacing: -.02em;
}

header p {
  margin: 6px 0 0;
  color: #d4dff5;
  font-size: 13px;
  opacity: .92;
}

.brand-row {
  display: flex;
  align-items: center;
  gap: 18px;
  max-width: 1180px;
  margin: auto;
  position: relative;
  padding-left: 90px; /* space for theme toggle button */
}

.logo-slot {
  width: 84px;
  height: 84px;
  flex: 0 0 84px;
  border: 2px dashed rgba(255,255,255,.3);
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background: rgba(255,255,255,.08);
  color: #eef2fb;
  font-size: 11px;
  text-align: center;
  backdrop-filter: blur(4px);
}

.logo-slot img { width: 100%; height: 100%; object-fit: contain; }

.brand-title-wrap { min-width: 0; flex: 1; }

.title-banner-wrap img {
  display: block;
  max-width: 100%;
  max-height: 100px;
  object-fit: contain;
  margin: 6px 0;
}

/* User chip */
.user-chip {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  margin-top: 10px;
  padding: 6px 12px;
  background: rgba(255,255,255,.12);
  border-radius: 999px;
  font-size: 13px;
  backdrop-filter: blur(6px);
}

.user-chip button {
  background: rgba(255,255,255,.18);
  color: white;
  padding: 4px 12px;
  font-size: 12px;
  border-radius: 999px;
}

.user-chip button:hover { background: rgba(255,255,255,.28); }

/* Theme toggle button in header */
.theme-toggle {
  position: absolute;
  top: 22px;
  left: 22px;
  z-index: 10;
  background: rgba(255,255,255,.15);
  border: 1px solid rgba(255,255,255,.2);
  color: white;
  border-radius: 999px;
  padding: 8px 14px;
  font: inherit;
  font-size: 12px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  backdrop-filter: blur(6px);
  transition: background .2s;
}

.theme-toggle:hover { background: rgba(255,255,255,.28); }

/* ===== TICKER ===== */
.ticker-shell {
  background: linear-gradient(90deg, #fff7df, #ffeec2);
  border-bottom: 1px solid #f0dda1;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 8px max(14px, calc((100% - 1180px)/2));
  overflow: hidden;
}

html[data-theme="dark"] .ticker-shell {
  background: linear-gradient(90deg, #2a2410, #38320e);
  border-bottom-color: #5a4a18;
}

.ticker-label {
  font-weight: 700;
  white-space: nowrap;
  color: #72500b;
  font-size: 12px;
  padding: 4px 10px;
  background: rgba(213,154,25,.18);
  border-radius: 999px;
}

html[data-theme="dark"] .ticker-label { color: #f0b040; background: rgba(213,154,25,.12); }

.ticker-window { overflow: hidden; white-space: nowrap; flex: 1; }

.ticker-track {
  display: inline-block;
  min-width: 100%;
  animation: tickerMove 28s linear infinite;
  color: #4d3c12;
  font-size: 13px;
}

html[data-theme="dark"] .ticker-track { color: #d4c088; }

.ticker-window:hover .ticker-track { animation-play-state: paused; }

@keyframes tickerMove {
  0% { transform: translateX(100%); }
  100% { transform: translateX(-100%); }
}

/* ===== LAYOUT ===== */
.wrap {
  max-width: 1180px;
  margin: 20px auto;
  padding: 0 14px;
}

.nav {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 16px;
  background: var(--white);
  padding: 8px;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--line);
}

.tab {
  border: 0;
  background: transparent;
  border-radius: var(--radius-md);
  padding: 10px 18px;
  cursor: pointer;
  font: inherit;
  font-weight: 600;
  color: var(--ink-soft);
  transition: all .2s;
  position: relative;
}

.tab:hover { background: var(--bg-alt); color: var(--ink); }

.tab.active {
  background: linear-gradient(135deg, var(--navy), var(--blue));
  color: white;
  box-shadow: var(--shadow-sm);
}

html[data-theme="dark"] .tab.active {
  background: linear-gradient(135deg, #131c3a, #1f2a52);
}

/* ===== PANELS & CARDS ===== */
.panel { display: none; }
.panel.active { display: block; animation: fadeIn .3s ease; }

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}

.card {
  background: var(--white);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  padding: 22px;
  margin-bottom: 16px;
  box-shadow: var(--shadow-sm);
  transition: box-shadow .2s;
}

.card:hover { box-shadow: var(--shadow-md); }

.card.collapsible .card-header {
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin: -22px -22px 16px;
  padding: 16px 22px;
  background: var(--bg-alt);
  border-radius: var(--radius-lg) var(--radius-lg) 0 0;
  border-bottom: 1px solid var(--line);
  transition: background .2s;
  user-select: none;
}

.card.collapsible .card-header:hover { background: var(--line-soft); }

.card.collapsible .card-header h2 { margin: 0; font-size: 17px; }

.card.collapsible .chevron {
  font-size: 18px;
  color: var(--muted);
  transition: transform .25s;
}

.card.collapsible.collapsed .card-header { border-radius: var(--radius-lg); }
.card.collapsible.collapsed .card-body { display: none; }
.card.collapsible.collapsed .chevron { transform: rotate(-90deg); }

.card-body { animation: fadeIn .2s ease; }

h2 {
  font-size: 19px;
  margin: 0 0 14px;
  color: var(--navy);
  font-weight: 700;
  letter-spacing: -.01em;
}

h3 {
  font-size: 15px;
  margin: 16px 0 8px;
  color: var(--navy);
  font-weight: 600;
}

/* ===== FORMS ===== */
.grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.grid.three { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.grid.full { grid-template-columns: 1fr; }

label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 6px;
  color: var(--ink-soft);
}

input, select, textarea {
  width: 100%;
  border: 1.5px solid var(--line);
  border-radius: var(--radius-md);
  padding: 11px 14px;
  font: inherit;
  background: var(--white);
  color: var(--ink);
  min-height: 44px;
  transition: border-color .2s, box-shadow .2s;
}

textarea { min-height: 90px; resize: vertical; }

input:focus, select:focus, textarea:focus {
  outline: none;
  border-color: var(--blue);
  box-shadow: 0 0 0 3px rgba(59,89,152,.15);
}

input[type="checkbox"], input[type="radio"] {
  width: auto;
  min-height: auto;
  margin: 0 6px 0 0;
}

input[type="color"] { padding: 4px; height: 44px; cursor: pointer; }
input[type="file"] { padding: 8px; }

button {
  font: inherit;
  font-weight: 600;
  cursor: pointer;
  border: 0;
  border-radius: var(--radius-md);
  padding: 11px 18px;
  background: linear-gradient(135deg, var(--navy), var(--blue));
  color: white;
  transition: transform .12s, box-shadow .2s, opacity .2s;
  box-shadow: var(--shadow-sm);
}

button:hover { transform: translateY(-1px); box-shadow: var(--shadow-md); }
button:active { transform: translateY(0); }
button:disabled { opacity: .5; cursor: not-allowed; }

button.secondary {
  background: var(--line-soft);
  color: var(--navy);
  box-shadow: none;
}

button.secondary:hover { background: var(--line); }

button.gold {
  background: linear-gradient(135deg, var(--gold), var(--gold-light));
  color: #1f2635;
}

button.danger {
  background: var(--red-bg);
  color: var(--red);
}

button.danger:hover { background: #fecaca; }

button.small { padding: 6px 12px; font-size: 12px; border-radius: var(--radius-sm); }

.actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 16px;
}

.hint { font-size: 12px; color: var(--muted); margin-top: 6px; line-height: 1.6; }

.notice {
  padding: 12px 16px;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, #fff7df, #ffefb8);
  border: 1px solid #f0dda1;
  font-size: 13px;
  margin-bottom: 16px;
  color: #72500b;
}

html[data-theme="dark"] .notice {
  background: linear-gradient(135deg, #2a2410, #38300c);
  border-color: #5a4a18;
  color: #f0b040;
}

/* ===== STATS ===== */
.stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.stat {
  background: var(--white);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  padding: 18px;
  text-align: center;
  transition: transform .2s, box-shadow .2s;
  position: relative;
  overflow: hidden;
}

.stat::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 3px;
  background: linear-gradient(90deg, var(--navy), var(--blue));
}

.stat:hover { transform: translateY(-2px); box-shadow: var(--shadow-md); }

.stat b {
  display: block;
  font-size: 28px;
  font-weight: 700;
  color: var(--navy);
  margin-bottom: 4px;
}

.stat span { font-size: 12px; color: var(--muted); }

/* ===== SERVICE LIST ===== */
.service-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.check {
  display: flex;
  align-items: center;
  gap: 8px;
  border: 1.5px solid var(--line);
  padding: 8px 12px;
  border-radius: var(--radius-md);
  font-size: 13px;
  background: var(--white);
  cursor: pointer;
  transition: all .2s;
}

.check:hover { border-color: var(--blue); background: var(--bg-alt); }

.check input { width: auto; min-height: auto; }

/* ===== TABLES ===== */
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

th, td {
  text-align: right;
  padding: 11px 14px;
  border-bottom: 1px solid var(--line);
  vertical-align: top;
}

th {
  background: var(--bg-alt);
  color: var(--navy);
  font-weight: 700;
  font-size: 12px;
  letter-spacing: .02em;
}

tr:hover td { background: var(--bg-alt); }

.table-wrap {
  overflow: auto;
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  max-height: 600px;
}

.badge {
  display: inline-block;
  background: linear-gradient(135deg, #eaf0fb, #d8e2f5);
  color: #344b7b;
  border-radius: 999px;
  padding: 3px 10px;
  font-size: 11px;
  margin: 2px;
  font-weight: 600;
}

html[data-theme="dark"] .badge { background: linear-gradient(135deg, #1d2a4d, #2a3a6a); color: #a9c0f5; }

.empty { padding: 32px; text-align: center; color: var(--muted); }

.footer {
  color: var(--muted);
  font-size: 12px;
  text-align: center;
  padding: 24px;
}

/* ===== DYNAMIC FIELDS ===== */
.dynamic-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  margin-top: 16px;
}

.dynamic-fields .wide { grid-column: 1/-1; }

/* ===== LOGIN PAGE — Classic CSS Background (no image) ===== */
.login-overlay {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  padding: 16px;
  /* Classic gradient background - no image, very lightweight */
  background:
    /* Subtle radial accents */
    radial-gradient(circle at 20% 20%, rgba(99, 140, 234, .25), transparent 50%),
    radial-gradient(circle at 80% 80%, rgba(213, 154, 25, .15), transparent 50%),
    /* Main diagonal gradient */
    linear-gradient(135deg, #1a2540 0%, #2d3f6e 50%, #1f2b50 100%);
  background-color: #1a2540;
  overflow: auto;
}

/* Subtle dot pattern overlay */
.login-overlay::before {
  content: '';
  position: absolute;
  inset: 0;
  background-image:
    radial-gradient(circle at 1px 1px, rgba(255,255,255,.04) 1px, transparent 0);
  background-size: 24px 24px;
  pointer-events: none;
  z-index: 0;
}

.login-overlay.hidden { display: none; }

/* (dark overlay removed - the gradient background is already dark enough) */
.login-bg-overlay { display: none; }

/* Brand image (title + logo) — exactly the same width as the login card, just above it */
.login-brand-wrap {
  position: relative;
  z-index: 3;
  width: 100%;
  max-width: 420px; /* exactly matches .login-card max-width */
  margin-top: 3vh;  /* small top margin from page top */
  text-align: center;
}

.login-brand-img,
.login-brand-wrap picture,
.login-brand-wrap img {
  display: block;
  width: 100%;        /* fill the brand-wrap (420px) — same width as login card */
  height: auto;
  border-radius: var(--radius-md) var(--radius-md) 0 0; /* flush with card top corners */
  filter: drop-shadow(0 6px 18px rgba(0,0,0,.35));
}

/* Login card — sits directly below the brand image with minimal gap */
.login-card {
  position: relative;
  z-index: 3;
  width: 100%;
  max-width: 420px;
  margin-top: 0; /* no gap — brand image connects flush to card */
  background: rgba(255,255,255,.97);
  border-radius: 0 0 var(--radius-xl) var(--radius-xl); /* rounded only at bottom */
  padding: 24px 28px 22px;
  box-shadow:
    0 32px 80px rgba(0,0,0,.5),
    0 12px 32px rgba(0,0,0,.3),
    0 0 0 1px rgba(255,255,255,.2);
  animation: cardIn .5s cubic-bezier(.22,1,.36,1);
  text-align: center;
  backdrop-filter: blur(20px);
  transition: box-shadow .2s, opacity .2s;
}
html[data-theme="dark"] .login-card {
  background: rgba(26,37,60,.95);
  color: var(--ink);
}

@keyframes cardIn {
  from { opacity: 0; transform: translateY(24px) scale(.96); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.login-banner {
  width: 100%;
  max-height: 130px;
  object-fit: cover;
  border-radius: var(--radius-md);
  margin-bottom: 18px;
}

/* Banner container — wraps admin-managed banner images above the login card */
.login-banner-container {
  width: 100%;
  max-width: 420px;
  margin-top: 4px;
  text-align: center;
}
.login-banner-container:empty { display: none; }
.login-banner-container img {
  display: block;
  width: 100%;
  max-height: 130px;
  object-fit: cover;
  border-radius: var(--radius-md);
  margin-bottom: 10px;
  box-shadow: 0 8px 24px rgba(0,0,0,.3);
}
.login-banner-container a {
  display: block;
}

/* Login announcements list — the bottom box below the login card */
.login-announcement-list {
  width: 100%;
  max-width: 420px;
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  z-index: 3;
  position: relative;
}
.login-announcement-list:empty { display: none; }

.login-announcement-item {
  background: rgba(255,255,255,.95);
  border-radius: var(--radius-md);
  padding: 12px 16px;
  font-size: 13.5px;
  line-height: 1.6;
  color: var(--ink, #1f2937);
  text-align: center;
  box-shadow: 0 6px 20px rgba(0,0,0,.25);
  border-right: 4px solid var(--accent, #3156a5);
  animation: cardIn .4s cubic-bezier(.22,1,.36,1);
}
.login-announcement-item.festive {
  background: linear-gradient(135deg, #fff8e6, #fff3d0);
  border-right-color: #d59a19;
  color: #72500b;
  font-weight: 500;
}
html[data-theme="dark"] .login-announcement-item {
  background: rgba(26,37,60,.95);
  color: var(--ink, #e5e7eb);
}
html[data-theme="dark"] .login-announcement-item.festive {
  background: linear-gradient(135deg, #2a2410, #38300c);
  color: #f0b040;
}

/* Login mark/title/subtitle hidden by default now — they're shown only if user customizes */
.login-mark { display: none; }
.login-title { display: none; }
.login-subtitle { display: none; }

.login-form {
  display: flex;
  flex-direction: column;
  gap: 13px;
  text-align: right;
}

.login-field { text-align: right; }

.login-field label {
  font-size: 13px;
  font-weight: 700;
  color: var(--ink-soft);
  margin-bottom: 6px;
  display: block;
  text-align: right;
}

.input-wrap {
  position: relative;
  display: flex;
  align-items: center;
}

.input-icon {
  position: absolute;
  right: 14px;
  color: var(--muted);
  pointer-events: none;
  transition: color .2s;
  flex-shrink: 0;
}

.input-wrap input {
  width: 100%;
  background: var(--bg);
  border: 1.5px solid var(--line);
  padding: 11px 44px 11px 44px;
  border-radius: var(--radius-md);
  transition: all .2s;
  font: inherit;
  color: var(--ink);
  min-height: 46px;
}

.input-wrap input:focus {
  background: var(--white);
  border-color: var(--blue);
  box-shadow: 0 0 0 4px rgba(59,89,152,.12);
}

.input-wrap input:focus ~ .input-icon {
  color: var(--blue);
}

.toggle-password {
  position: absolute;
  left: 8px;
  background: transparent;
  border: 0;
  color: var(--muted);
  cursor: pointer;
  padding: 6px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: none;
}

.toggle-password:hover { color: var(--blue); background: var(--bg-alt); }

.login-forgot-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12.5px;
}

.login-remember {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--ink-soft);
  cursor: pointer;
}

.login-remember input {
  width: auto;
  min-height: auto;
  margin: 0;
  accent-color: var(--blue);
}

.login-forgot-row a {
  color: var(--blue);
  text-decoration: none;
  font-weight: 600;
  transition: color .2s;
}

.login-forgot-row a:hover { color: var(--navy); text-decoration: underline; }

.login-actions { margin-top: 2px; }

.login-actions button {
  width: 100%;
  background: linear-gradient(135deg, var(--blue), var(--navy));
  padding: 12px;
  font-size: 15px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  position: relative;
  overflow: hidden;
}

.login-actions button::before {
  content: '';
  position: absolute;
  top: 0; left: -100%;
  width: 100%; height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,.2), transparent);
  transition: left .6s;
}

.login-actions button:hover::before { left: 100%; }

.login-actions button svg { transition: transform .2s; }
.login-actions button:hover svg { transform: translateX(-4px); }

.login-error {
  color: var(--red);
  font-size: 13px;
  min-height: 18px;
  margin-top: 4px;
  padding: 8px 12px;
  background: var(--red-bg);
  border-radius: var(--radius-sm);
  text-align: right;
  display: none;
}

.login-error:not(:empty) { display: block; animation: shake .3s; }

@keyframes shake {
  0%, 100% { transform: translateX(0); }
  25% { transform: translateX(-4px); }
  75% { transform: translateX(4px); }
}

.login-demo {
  font-size: 12.5px;
  background: linear-gradient(135deg, #fff8e6, #fff3d0);
  border-radius: var(--radius-md);
  padding: 11px 13px;
  border: 1px solid #f0dda1;
  color: #72500b;
  display: flex;
  align-items: center;
  gap: 10px;
  text-align: right;
  margin-top: 14px;
}

html[data-theme="dark"] .login-demo {
  background: linear-gradient(135deg, #2a2410, #38300c);
  border-color: #5a4a18;
  color: #f0b040;
}

.login-demo-icon {
  width: 30px;
  height: 30px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(213,154,25,.18);
  border-radius: var(--radius-sm);
  color: #d59a19;
}

html[data-theme="dark"] .login-demo-icon { color: #f0b040; }

.login-demo b { color: var(--navy); font-weight: 700; }
html[data-theme="dark"] .login-demo b { color: var(--ink); }

.login-extra { margin-top: 12px; font-size: 13px; color: var(--muted); }
.login-separator { color: var(--muted); margin: 0 6px; }

/* Theme toggle button is hidden on login page per user request */
.login-theme-toggle { display: none !important; }

/* ===== CHART AREA ===== */
.chart-container {
  background: var(--white);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  padding: 22px;
  margin-bottom: 16px;
  box-shadow: var(--shadow-sm);
}

.chart-container h2 { margin-top: 0; }

.chart-canvas-wrap {
  position: relative;
  height: 280px;
  margin-top: 14px;
}

@media (max-width: 700px) {
  .chart-canvas-wrap { height: 240px; }
}

/* ===== RESPONSIVE ===== */
@media (max-width: 700px) {
  .grid, .grid.three { grid-template-columns: 1fr; }
  .stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .card { padding: 16px; }
  .wrap { margin-top: 12px; padding: 0 10px; }
  header { padding: 18px; padding-top: 50px; }
  .brand-row { gap: 12px; padding-left: 0; }
  .logo-slot { width: 60px; height: 60px; flex-basis: 60px; }
  .ticker-shell { gap: 8px; padding: 8px 12px; }
  .dynamic-fields { grid-template-columns: 1fr; }
  .tab { padding: 8px 12px; font-size: 13px; }
  .login-card { padding: 20px 22px 18px; }
  .login-brand-wrap { margin-top: 4vh; max-width: 95%; }
  .theme-toggle { top: 14px; left: 14px; padding: 6px 10px; font-size: 11px; }
}

@media (max-width: 480px) {
  .stats { grid-template-columns: 1fr; }
  .nav { gap: 4px; padding: 6px; }
  .tab { padding: 7px 10px; font-size: 11.5px; }
  .login-card { padding: 18px 18px 16px; }
  .login-brand-wrap { margin-top: 3vh; max-width: 98%; }
}

/* ===== UTILITY ===== */
.toast {
  position: fixed;
  bottom: 20px;
  right: 20px;
  background: var(--white);
  color: var(--ink);
  padding: 14px 18px;
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  border: 1px solid var(--line);
  z-index: 1000;
  font-size: 13px;
  animation: toastIn .3s ease;
  max-width: 320px;
}

.toast.success { border-right: 4px solid var(--green); }
.toast.error { border-right: 4px solid var(--red); }

@keyframes toastIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Loader */
.loader {
  display: inline-block;
  width: 18px;
  height: 18px;
  border: 2px solid var(--line);
  border-top-color: var(--blue);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

/* Settings sections list */
.admin-section-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}

.admin-section-link {
  background: var(--white);
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  padding: 12px 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  transition: all .2s;
}

.admin-section-link:hover {
  border-color: var(--blue);
  background: var(--bg-alt);
}

.admin-section-link .arrow {
  color: var(--muted);
  font-size: 18px;
}
