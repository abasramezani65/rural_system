-- PostgreSQL schema for Rural Services System
-- This schema is used when DATABASE_URL environment variable is set to a PostgreSQL connection string.

-- Roles (سمت‌ها)
CREATE TABLE IF NOT EXISTS roles (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Services (خدمات)
CREATE TABLE IF NOT EXISTS services (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Provinces (استان‌ها)
CREATE TABLE IF NOT EXISTS provinces (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Counties (شهرستان‌ها)
CREATE TABLE IF NOT EXISTS counties (
  id TEXT PRIMARY KEY,
  province_id TEXT NOT NULL,
  name TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (province_id) REFERENCES provinces(id) ON DELETE CASCADE,
  UNIQUE(province_id, name)
);

-- Districts (دهستان‌ها)
CREATE TABLE IF NOT EXISTS districts (
  id TEXT PRIMARY KEY,
  county_id TEXT NOT NULL,
  name TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
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
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (province_id) REFERENCES provinces(id) ON DELETE SET NULL,
  FOREIGN KEY (county_id) REFERENCES counties(id) ON DELETE SET NULL
);

-- Sessions (نشست‌ها)
CREATE TABLE IF NOT EXISTS sessions (
  token TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expires_at TIMESTAMP NOT NULL,
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
  custom_values TEXT,
  created_by_user_id TEXT,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
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
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Custom Fields (فیلدهای سفارشی)
CREATE TABLE IF NOT EXISTS custom_fields (
  id TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  type TEXT NOT NULL DEFAULT 'text',
  scope TEXT NOT NULL DEFAULT 'all',
  active INTEGER NOT NULL DEFAULT 1,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Settings (key-value)
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT
);

-- Geo Catalog (تقسیمات کشوری)
CREATE TABLE IF NOT EXISTS geo_catalog (
  id TEXT PRIMARY KEY,
  province_name TEXT NOT NULL,
  county_name TEXT NOT NULL,
  district_name TEXT,
  village_name TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(province_name, county_name, district_name, village_name)
);

-- Login demo box items
CREATE TABLE IF NOT EXISTS login_demo_items (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  content TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1,
  sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Login announcements
CREATE TABLE IF NOT EXISTS login_announcements (
  id TEXT PRIMARY KEY,
  text TEXT NOT NULL,
  festive INTEGER NOT NULL DEFAULT 0,
  active INTEGER NOT NULL DEFAULT 1,
  sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Login banners
CREATE TABLE IF NOT EXISTS login_banners (
  id TEXT PRIMARY KEY,
  image_data TEXT NOT NULL,
  image_mime TEXT NOT NULL DEFAULT 'image/png',
  link_url TEXT DEFAULT '',
  title TEXT DEFAULT '',
  active INTEGER NOT NULL DEFAULT 1,
  sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Core field config
CREATE TABLE IF NOT EXISTS core_fields (
  field_key TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  visible INTEGER NOT NULL DEFAULT 1
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_records_province ON records(province_id);
CREATE INDEX IF NOT EXISTS idx_records_county ON records(county_id);
CREATE INDEX IF NOT EXISTS idx_records_service ON records(service_id);
CREATE INDEX IF NOT EXISTS idx_records_village ON records(village);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);
