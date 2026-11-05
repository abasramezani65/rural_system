-- SQLite schema for Rural Services System
-- SQLite uses WRITE locks at the file level, but WAL mode allows concurrent reads
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- Roles (سمت‌ها)
CREATE TABLE IF NOT EXISTS roles (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Services (خدمات)
CREATE TABLE IF NOT EXISTS services (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Provinces (استان‌ها)
CREATE TABLE IF NOT EXISTS provinces (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Counties (شهرستان‌ها)
CREATE TABLE IF NOT EXISTS counties (
  id TEXT PRIMARY KEY,
  province_id TEXT NOT NULL,
  name TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (province_id) REFERENCES provinces(id) ON DELETE CASCADE,
  UNIQUE(province_id, name)
);

-- Districts (دهستان‌ها) - optional
CREATE TABLE IF NOT EXISTS districts (
  id TEXT PRIMARY KEY,
  county_id TEXT NOT NULL,
  name TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (county_id) REFERENCES counties(id) ON DELETE CASCADE
);

-- Users (کاربران)
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  username TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('national','provincial','county')),
  province_id TEXT,
  county_id TEXT,
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (province_id) REFERENCES provinces(id) ON DELETE SET NULL,
  FOREIGN KEY (county_id) REFERENCES counties(id) ON DELETE SET NULL
);

-- Sessions (نشست‌ها)
CREATE TABLE IF NOT EXISTS sessions (
  token TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  expires_at TEXT NOT NULL,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Records (سوابق خدمات)
CREATE TABLE IF NOT EXISTS records (
  id TEXT PRIMARY KEY,
  expert_name TEXT,
  role_id TEXT,
  role_name TEXT,
  org TEXT,
  province_id TEXT,
  province_name TEXT,
  county_id TEXT,
  county_name TEXT,
  district_id TEXT,
  district_name TEXT,
  village TEXT NOT NULL,
  service_id TEXT,
  service_name TEXT,
  service_date TEXT,
  beneficiaries INTEGER DEFAULT 0,
  description TEXT,
  evidence TEXT,
  custom_values TEXT,  -- JSON object
  created_by_user_id TEXT,
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (province_id) REFERENCES provinces(id) ON DELETE SET NULL,
  FOREIGN KEY (county_id) REFERENCES counties(id) ON DELETE SET NULL,
  FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE SET NULL,
  FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE SET NULL,
  FOREIGN KEY (created_by_user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- Announcements (اعلان‌ها)
CREATE TABLE IF NOT EXISTS announcements (
  id TEXT PRIMARY KEY,
  text TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Custom Fields (فیلدهای سفارشی)
CREATE TABLE IF NOT EXISTS custom_fields (
  id TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  type TEXT NOT NULL DEFAULT 'text',
  scope TEXT NOT NULL DEFAULT 'all',  -- 'all' or service_id
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Settings (key-value) - تنظیمات سامانه
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT
);

-- Geo Catalog (تقسیمات کشوری - روستاها)
CREATE TABLE IF NOT EXISTS geo_catalog (
  id TEXT PRIMARY KEY,
  province_name TEXT NOT NULL,
  county_name TEXT NOT NULL,
  district_name TEXT,
  village_name TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(province_name, county_name, district_name, village_name)
);

-- Login announcements (پیام‌های مناسبتی روی صفحه ورود)
CREATE TABLE IF NOT EXISTS login_announcements (
  id TEXT PRIMARY KEY,
  text TEXT NOT NULL,
  festive INTEGER NOT NULL DEFAULT 0,
  active INTEGER NOT NULL DEFAULT 1,
  sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Login banners (بنر تصویری روی صفحه ورود)
CREATE TABLE IF NOT EXISTS login_banners (
  id TEXT PRIMARY KEY,
  image_data TEXT NOT NULL,
  image_mime TEXT NOT NULL DEFAULT 'image/jpeg',
  link_url TEXT DEFAULT '',
  title TEXT DEFAULT '',
  active INTEGER NOT NULL DEFAULT 1,
  sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Core field config (عناوین فیلدهای اصلی)
CREATE TABLE IF NOT EXISTS core_fields (
  field_key TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  visible INTEGER NOT NULL DEFAULT 1
);

-- ===== PLAN MANAGEMENT SYSTEM (سامانه طرح‌های پویا) =====

CREATE TABLE IF NOT EXISTS plans (
  id              TEXT PRIMARY KEY,
  name            TEXT NOT NULL,
  description     TEXT,
  active          INTEGER NOT NULL DEFAULT 1,
  allow_duplicate INTEGER NOT NULL DEFAULT 0,
  sort_order      INTEGER NOT NULL DEFAULT 0,
  created_by      TEXT,
  created_at      TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS plan_status_allowed (
  id              TEXT PRIMARY KEY,
  plan_id         TEXT NOT NULL,
  status_category TEXT NOT NULL,
  UNIQUE(plan_id, status_category),
  FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS plan_fields (
  id          TEXT PRIMARY KEY,
  plan_id     TEXT NOT NULL,
  field_key   TEXT NOT NULL,
  label       TEXT NOT NULL,
  type        TEXT NOT NULL DEFAULT 'text',
  required    INTEGER NOT NULL DEFAULT 0,
  options     TEXT,
  help_text   TEXT,
  sort_order  INTEGER NOT NULL DEFAULT 0,
  active      INTEGER NOT NULL DEFAULT 1,
  created_at  TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS plan_records (
  id              TEXT PRIMARY KEY,
  plan_id         TEXT NOT NULL,
  province_id     TEXT,
  county_id       TEXT,
  district_id     TEXT,
  village         TEXT NOT NULL,
  status_category TEXT NOT NULL,
  field_values    TEXT,
  expert_name     TEXT,
  role_id         TEXT,
  org             TEXT,
  service_date    TEXT,
  description     TEXT,
  created_by      TEXT,
  created_at      TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(plan_id, village, province_id, county_id),
  FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE SET NULL,
  FOREIGN KEY (province_id) REFERENCES provinces(id) ON DELETE SET NULL,
  FOREIGN KEY (county_id) REFERENCES counties(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS plan_status_history (
  id              TEXT PRIMARY KEY,
  plan_record_id  TEXT NOT NULL,
  old_status      TEXT,
  new_status      TEXT NOT NULL,
  changed_by      TEXT,
  changed_at      TEXT NOT NULL DEFAULT (datetime('now')),
  note            TEXT,
  FOREIGN KEY (plan_record_id) REFERENCES plan_records(id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_records_province ON records(province_id);
CREATE INDEX IF NOT EXISTS idx_records_county ON records(county_id);
CREATE INDEX IF NOT EXISTS idx_records_service ON records(service_id);
CREATE INDEX IF NOT EXISTS idx_records_village ON records(village);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_plan_records_plan ON plan_records(plan_id);
CREATE INDEX IF NOT EXISTS idx_plan_records_village ON plan_records(village);
CREATE INDEX IF NOT EXISTS idx_plan_records_status ON plan_records(status_category);
CREATE INDEX IF NOT EXISTS idx_plan_fields_plan ON plan_fields(plan_id);
CREATE INDEX IF NOT EXISTS idx_plan_status_allowed_plan ON plan_status_allowed(plan_id);

CREATE TABLE IF NOT EXISTS password_reset_requests (
  id          TEXT PRIMARY KEY,
  user_id     TEXT,
  user_name   TEXT NOT NULL,
  username    TEXT NOT NULL,
  province_id TEXT,
  county_id   TEXT,
  user_role   TEXT,
  status      TEXT NOT NULL DEFAULT 'pending',
  created_at  TEXT NOT NULL DEFAULT (datetime('now')),
  reviewed_by TEXT,
  reviewed_at TEXT
);

CREATE TABLE IF NOT EXISTS messages (
  id TEXT PRIMARY KEY, sender_id TEXT NOT NULL, sender_name TEXT, sender_role TEXT,
  target_role TEXT NOT NULL, target_province_id TEXT, target_county_id TEXT,
  subject TEXT NOT NULL, body TEXT NOT NULL, is_read INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
