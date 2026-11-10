"""Database helpers for the Rural Services System.

Supports both SQLite (local development) and PostgreSQL (production).
The database type is auto-detected:
- If DATABASE_URL environment variable is set → PostgreSQL
- Otherwise → SQLite (local file)
"""
import os
import json
import threading
import secrets
import time
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

# Detect database type
# Only use PostgreSQL if DATABASE_URL starts with postgres:// or postgresql://
_raw_db_url = os.environ.get('DATABASE_URL', '')
IS_POSTGRES = _raw_db_url.startswith('postgres://') or _raw_db_url.startswith('postgresql://')
DATABASE_URL = _raw_db_url if IS_POSTGRES else ''

DB_PATH = os.environ.get('RURAL_DB_PATH', os.path.join(os.path.dirname(__file__), 'rural.db'))
SCHEMA_SQLITE_PATH = os.path.join(os.path.dirname(__file__), 'schema.sql')
SCHEMA_PG_PATH = os.path.join(os.path.dirname(__file__), 'schema_pg.sql')

_local = threading.local()


def _is_connection_alive(conn):
    """Check if a PostgreSQL connection is still usable (Supabase pooler may close idle ones)."""
    try:
        cur = conn.cursor()
        cur.execute('SELECT 1')
        cur.close()
        return True
    except Exception:
        return False


def _new_pg_conn():
    """Create a fresh PostgreSQL connection."""
    import psycopg2
    from psycopg2.extras import RealDictCursor
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    conn.cursor_factory = RealDictCursor
    return conn


def get_conn():
    """Return a per-thread connection.
    - PostgreSQL: psycopg2 connection with RealDictCursor
      (reconnects automatically if the cached connection went stale due to Supabase pooler idle timeout)
    - SQLite: sqlite3 connection with Row factory
    """
    if hasattr(_local, 'conn'):
        if IS_POSTGRES:
            # Verify cached connection is still alive; reconnect if stale
            if _is_connection_alive(_local.conn):
                return _local.conn
            else:
                try:
                    _local.conn.close()
                except Exception:
                    pass
                del _local.conn
        else:
            return _local.conn

    if IS_POSTGRES:
        _local.conn = _new_pg_conn()
    else:
        import sqlite3
        _local.conn = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute('PRAGMA journal_mode=WAL;')
        _local.conn.execute('PRAGMA foreign_keys=ON;')
        _local.conn.execute('PRAGMA busy_timeout=5000;')
    return _local.conn


def _is_conn_error(e):
    """Check if an exception is a connection-level error worth retrying."""
    if not IS_POSTGRES:
        return False
    msg = str(e).lower()
    return ('ssl' in msg or 'connection' in msg or 'eof' in msg
            or 'bad record' in msg or 'closed' in msg)


def _convert_sql(sql):
    """Convert SQLite-style ? placeholders to PostgreSQL %s placeholders."""
    if IS_POSTGRES:
        return sql.replace('?', '%s')
    return sql


def _exec(sql, params=None):
    """Execute a single SQL statement. Returns cursor.
    Retries once on stale PostgreSQL connection (Supabase pooler timeout)."""
    sql = _convert_sql(sql)
    try:
        conn = get_conn()
        if IS_POSTGRES:
            cur = conn.cursor()
            cur.execute(sql, params or ())
            return cur
        else:
            return conn.execute(sql, params or ())
    except Exception as e:
        if _is_conn_error(e):
            # Stale connection — force reconnect and retry once
            if hasattr(_local, 'conn'):
                try:
                    _local.conn.close()
                except Exception:
                    pass
                del _local.conn
            conn = get_conn()
            if IS_POSTGRES:
                cur = conn.cursor()
                cur.execute(sql, params or ())
                return cur
            else:
                return conn.execute(sql, params or ())
        raise


def _execmany(sql, seq_of_params):
    """Execute many. Returns cursor. Retries on stale PostgreSQL connection."""
    sql = _convert_sql(sql)
    try:
        conn = get_conn()
        if IS_POSTGRES:
            cur = conn.cursor()
            cur.executemany(sql, seq_of_params)
            return cur
        else:
            return conn.executemany(sql, seq_of_params)
    except Exception as e:
        if _is_conn_error(e):
            if hasattr(_local, 'conn'):
                try:
                    _local.conn.close()
                except Exception:
                    pass
                del _local.conn
            conn = get_conn()
            if IS_POSTGRES:
                cur = conn.cursor()
                cur.executemany(sql, seq_of_params)
                return cur
            else:
                return conn.executemany(sql, seq_of_params)
        raise


def _execscript(sql_script):
    """Execute a script (multiple statements). For schema initialization."""
    conn = get_conn()
    if IS_POSTGRES:
        cur = conn.cursor()
        # Split by semicolons and execute each statement
        # Remove PRAGMA lines (PostgreSQL doesn't use them)
        lines = sql_script.split('\n')
        cleaned = []
        for line in lines:
            if line.strip().startswith('PRAGMA'):
                continue
            cleaned.append(line)
        sql_script = '\n'.join(cleaned)
        cur.execute(sql_script)
        cur.close()
    else:
        conn.executescript(sql_script)


def _fetchone(sql, params=None):
    """Execute and fetch one row. Returns dict or None."""
    cur = _exec(sql, params)
    row = cur.fetchone()
    if IS_POSTGRES:
        cur.close()
    return dict(row) if row else None


def _fetchall(sql, params=None):
    """Execute and fetch all rows. Returns list of dicts."""
    cur = _exec(sql, params)
    rows = cur.fetchall()
    if IS_POSTGRES:
        cur.close()
    return [dict(r) for r in rows]


def _fetchval(sql, params=None):
    """Execute and fetch a single value (first column of first row)."""
    row = _fetchone(sql, params)
    if row:
        return list(row.values())[0]
    return None


def init_db():
    """Initialize the database schema and seed default data."""
    schema_path = SCHEMA_PG_PATH if IS_POSTGRES else SCHEMA_SQLITE_PATH
    with open(schema_path, 'r', encoding='utf-8') as f:
        schema_sql = f.read()
    _execscript(schema_sql)
    _run_migrations()
    _seed_defaults()
    db_info = f'PostgreSQL: {DATABASE_URL[:50]}...' if IS_POSTGRES else f'SQLite at {DB_PATH}'
    print(f'[db] initialized ({db_info})')


def _column_exists(table, column):
    """Check if a column exists in a table (works for both SQLite and PostgreSQL)."""
    if IS_POSTGRES:
        row = _fetchone(
            "SELECT column_name FROM information_schema.columns WHERE table_name=%s AND column_name=%s",
            (table, column)
        )
        return row is not None
    else:
        # SQLite: use PRAGMA table_info
        rows = _fetchall(f'PRAGMA table_info({table})')
        return any(r['name'] == column for r in rows)


def _run_migrations():
    """Add new columns to existing tables for backward compatibility."""
    # geo_catalog: add section_name
    if not _column_exists('geo_catalog', 'section_name'):
        try:
            _exec('ALTER TABLE geo_catalog ADD COLUMN section_name TEXT')
        except Exception:
            pass  # column may already exist
    # plan_records: add section_id
    if not _column_exists('plan_records', 'section_id'):
        try:
            _exec('ALTER TABLE plan_records ADD COLUMN section_id TEXT')
        except Exception:
            pass
    # districts: add section_id
    if not _column_exists('districts', 'section_id'):
        try:
            _exec('ALTER TABLE districts ADD COLUMN section_id TEXT')
        except Exception:
            pass


def _seed_defaults():
    """Seed default roles, services, settings, and admin user if empty."""
    # Roles
    if _fetchval('SELECT COUNT(*) FROM roles') == 0:
        _execmany(
            'INSERT INTO roles(id, name, active) VALUES (?,?,?)',
            [('r1', 'کارشناس شهرستان', 1),
             ('r2', 'مسئول استانی', 1),
             ('r3', 'کارشناس کشوری', 1)]
        )
    # Services
    if _fetchval('SELECT COUNT(*) FROM services') == 0:
        _execmany(
            'INSERT INTO services(id, name, active) VALUES (?,?,?)',
            [('s1', 'آبرسانی', 1),
             ('s2', 'اشتغال‌زایی', 1),
             ('s3', 'بهسازی راه', 1)]
        )
    # Provinces & counties - one default
    if _fetchval('SELECT COUNT(*) FROM provinces') == 0:
        _exec("INSERT INTO provinces(id, name) VALUES ('p1','نمونه استان')")
        _exec("INSERT INTO counties(id, province_id, name) VALUES ('c1','p1','نمونه شهرستان')")
    # Admin user
    row = _fetchone("SELECT id FROM users WHERE username='admin'")
    if not row:
        _exec(
            "INSERT INTO users(id, name, username, password_hash, role, province_id, county_id, active) VALUES (?,?,?,?,?,?,?,?)",
            ('u_admin_default', 'مدیر سامانه', 'admin', generate_password_hash('admin12345'), 'national', None, None, 1)
        )
    else:
        _exec(
            "UPDATE users SET password_hash=?, role='national', active=1, province_id=NULL, county_id=NULL WHERE username='admin'",
            (generate_password_hash('admin12345'),)
        )
    # Settings defaults
    default_settings = {
        'title': 'سامانه پایش و معرفی روستاهای برخوردار از خدمات',
        'subtitle': 'ثبت خدمات در سطح شهرستان، استان و کشور | مدیریت اطلاعات پایه | فیلتر و گزارش‌گیری',
        'logo': '',
        'banner': '',
        'loginBanner': '',
        'loginMark': '',
        'loginHeading': 'سامانه جمع‌آوری و پایش خدمات روستایی',
        'loginSubtitle': '۱۰۰۰ روستای خوداتکا',
        'loginButton': 'ورود',
        'loginUsernameLabel': 'نام کاربری',
        'loginPasswordLabel': 'رمز عبور',
        'loginDemoText': 'ورود با حساب آزمایشی',
        'loginContactText': 'راهنما / پشتیبانی',
        'loginContactUrl': '',
        'loginBg': '#263b70',
        'loginAccent': '#3156a5',
        'loginBackgroundPreset': 'hero',
        'loginExtra': '',
        'showLoginDemoNotice': '1',
        'evidenceEnabled': '1',
    }
    for k, v in default_settings.items():
        if not _fetchone('SELECT key FROM settings WHERE key=?', (k,)):
            _exec('INSERT INTO settings(key, value) VALUES (?,?)', (k, v))
    # Core fields defaults
    default_core_fields = {
        'expertName': ('نام و نام خانوادگی کارشناس', 1),
        'expertRole': ('سمت / سطح فعالیت', 1),
        'org': ('واحد یا مجموعه مجری', 1),
        'province': ('استان', 1),
        'county': ('شهرستان', 1),
        'district': ('دهستان', 1),
        'village': ('روستا', 1),
        'service': ('خدمت انجام‌شده', 1),
        'serviceDate': ('تاریخ اجرا', 1),
        'beneficiaries': ('تعداد بهره‌مندان', 1),
        'description': ('شرح اقدام و نتیجه خدمت', 1),
        'evidence': ('لینک مستندات', 1),
    }
    for k, (label, visible) in default_core_fields.items():
        if not _fetchone('SELECT field_key FROM core_fields WHERE field_key=?', (k,)):
            _exec('INSERT INTO core_fields(field_key, label, visible) VALUES (?,?,?)',
                         (k, label, visible))


# ----- helpers -----
def uid(prefix='id'):
    import secrets, time
    return f'{prefix}_{int(time.time()*1000)}_{secrets.token_hex(4)}'


def now_iso():
    return datetime.utcnow().isoformat() + 'Z'


def to_dict(row):
    return dict(row) if row else None


def rows_to_dicts(rows):
    return [dict(r) for r in rows]


# ----- Sessions -----
SESSION_TTL_HOURS = 12


def create_session(user_id):
    import secrets
    token = secrets.token_urlsafe(32)
    expires = (datetime.utcnow() + timedelta(hours=SESSION_TTL_HOURS)).isoformat() + 'Z'
    conn = get_conn()
    _exec('INSERT INTO sessions(token, user_id, expires_at) VALUES (?,?,?)',
                 (token, user_id, expires))
    return token


def get_session_user(token):
    if not token:
        return None
    row = _fetchone(
        'SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id '
        'WHERE s.token=? AND s.expires_at > CURRENT_TIMESTAMP AND u.active=1',
        (token,)
    )
    return to_dict(row)


def destroy_session(token):
    if not token:
        return
    _exec('DELETE FROM sessions WHERE token=?', (token,))


def cleanup_sessions():
    _exec('DELETE FROM sessions WHERE expires_at <= CURRENT_TIMESTAMP')


# ----- Users -----
def list_users():
    conn = get_conn()
    rows = _fetchall('SELECT id, name, username, role, province_id, county_id, active, created_at FROM users ORDER BY created_at')
    return rows_to_dicts(rows)


def list_users_by_province(province_id):
    """List users belonging to a specific province (for provincial admin scope)."""
    conn = get_conn()
    rows = _fetchall(
        'SELECT id, name, username, role, province_id, county_id, active, created_at '
        'FROM users WHERE province_id=? ORDER BY created_at',
        (province_id,)
    )
    return rows_to_dicts(rows)


def get_user_by_username(username):
    conn = get_conn()
    row = _fetchone('SELECT * FROM users WHERE username=?', (username,))
    return to_dict(row)


def get_user(user_id):
    conn = get_conn()
    row = _fetchone('SELECT id, name, username, role, province_id, county_id, active FROM users WHERE id=?', (user_id,))
    return to_dict(row)


def create_user(name, username, password, role, province_id='', county_id=''):
    conn = get_conn()
    user_id = uid('u')
    pw_hash = generate_password_hash(password)
    _exec(
        'INSERT INTO users(id, name, username, password_hash, role, province_id, county_id, active) '
        'VALUES (?,?,?,?,?,?,?,1)',
        (user_id, name, username, pw_hash, role, province_id or None, county_id or None)
    )
    return user_id


def update_user(user_id, name, username, password, role, province_id='', county_id='', active=1):
    conn = get_conn()
    pid = province_id or None
    cid = county_id or None
    if password:
        pw_hash = generate_password_hash(password)
        _exec(
            'UPDATE users SET name=?, username=?, password_hash=?, role=?, province_id=?, county_id=?, active=? WHERE id=?',
            (name, username, pw_hash, role, pid, cid, active, user_id)
        )
    else:
        _exec(
            'UPDATE users SET name=?, username=?, role=?, province_id=?, county_id=?, active=? WHERE id=?',
            (name, username, role, pid, cid, active, user_id)
        )


def delete_user(user_id):
    if user_id == 'u_admin_default':
        return False  # protect admin
    conn = get_conn()
    _exec('DELETE FROM users WHERE id=?', (user_id,))
    return True


def toggle_user(user_id, active):
    conn = get_conn()
    _exec('UPDATE users SET active=? WHERE id=?', (1 if active else 0, user_id))


def verify_password(user, password):
    if not user:
        return False
    return check_password_hash(user['password_hash'], password)


# ----- Roles -----
def list_roles(active_only=False):
    conn = get_conn()
    sql = 'SELECT * FROM roles'
    if active_only:
        sql += ' WHERE active=1'
    sql += ' ORDER BY created_at'
    return rows_to_dicts(_fetchall(sql))


def add_role(name):
    rid = uid('r')
    conn = get_conn()
    _exec('INSERT INTO roles(id, name, active) VALUES (?,?,1)', (rid, name))
    return rid


def update_role(rid, name=None, active=None):
    conn = get_conn()
    if name is not None:
        _exec('UPDATE roles SET name=? WHERE id=?', (name, rid))
    if active is not None:
        _exec('UPDATE roles SET active=? WHERE id=?', (1 if active else 0, rid))


def delete_role(rid):
    conn = get_conn()
    _exec('DELETE FROM roles WHERE id=?', (rid,))


# ----- Services -----
def list_services(active_only=False):
    conn = get_conn()
    sql = 'SELECT * FROM services'
    if active_only:
        sql += ' WHERE active=1'
    sql += ' ORDER BY created_at'
    return rows_to_dicts(_fetchall(sql))


def add_service(name):
    sid = uid('s')
    conn = get_conn()
    _exec('INSERT INTO services(id, name, active) VALUES (?,?,1)', (sid, name))
    return sid


def update_service(sid, name=None, active=None):
    conn = get_conn()
    if name is not None:
        _exec('UPDATE services SET name=? WHERE id=?', (name, sid))
    if active is not None:
        _exec('UPDATE services SET active=? WHERE id=?', (1 if active else 0, sid))


def delete_service(sid):
    conn = get_conn()
    _exec('DELETE FROM services WHERE id=?', (sid,))


# ----- Provinces & Counties -----
def list_provinces():
    conn = get_conn()
    rows = _fetchall('SELECT * FROM provinces ORDER BY name')
    provinces = rows_to_dicts(rows)
    for p in provinces:
        counties = _fetchall('SELECT * FROM counties WHERE province_id=? ORDER BY name', (p['id'],))
        p['counties'] = rows_to_dicts(counties)
        # Attach sections (بخش‌ها) to each county
        for c in p['counties']:
            sections = _fetchall('SELECT * FROM sections WHERE county_id=? ORDER BY name', (c['id'],))
            c['sections'] = rows_to_dicts(sections)
            # Attach districts (دهستان‌ها) to each county
            districts = _fetchall('SELECT * FROM districts WHERE county_id=? ORDER BY name', (c['id'],))
            c['districts'] = rows_to_dicts(districts)
    return provinces


def add_province(name):
    pid = uid('p')
    conn = get_conn()
    _exec('INSERT INTO provinces(id, name) VALUES (?,?)', (pid, name))
    return pid


def add_county(province_id, name):
    cid = uid('c')
    conn = get_conn()
    _exec('INSERT INTO counties(id, province_id, name) VALUES (?,?,?)', (cid, province_id, name))
    return cid


def add_section(county_id, name):
    """Add a section (بخش) to a county."""
    sid = uid('sec')
    _exec('INSERT INTO sections(id, county_id, name) VALUES (?,?,?)', (sid, county_id, name))
    return sid


def delete_section(sid):
    _exec('DELETE FROM sections WHERE id=?', (sid,))


def list_sections_by_county(county_id):
    rows = _fetchall('SELECT * FROM sections WHERE county_id=? ORDER BY name', (county_id,))
    return rows_to_dicts(rows)


def delete_province(pid):
    conn = get_conn()
    _exec('DELETE FROM provinces WHERE id=?', (pid,))


def delete_county(cid):
    conn = get_conn()
    _exec('DELETE FROM counties WHERE id=?', (cid,))


# ----- Records -----
def list_records(filters=None):
    """filters: dict with possible keys: province_id, county_id, service_ids (list), mode (all/any), village"""
    conn = get_conn()
    sql = 'SELECT * FROM records'
    where = []
    params = []
    if filters:
        if filters.get('province_id'):
            where.append('province_id=?')
            params.append(filters['province_id'])
        if filters.get('county_id'):
            where.append('county_id=?')
            params.append(filters['county_id'])
        if filters.get('village'):
            where.append('village LIKE ?')
            params.append(f"%{filters['village']}%")
    if where:
        sql += ' WHERE ' + ' AND '.join(where)
    sql += ' ORDER BY created_at DESC'
    rows = _fetchall(sql, params)
    records = rows_to_dicts(rows)
    # Parse custom_values JSON
    for r in records:
        if r.get('custom_values'):
            try:
                r['custom_values'] = json.loads(r['custom_values'])
            except Exception:
                r['custom_values'] = {}
        else:
            r['custom_values'] = {}
        r['beneficiaries'] = int(r.get('beneficiaries') or 0)
    return records


def get_record(record_id):
    conn = get_conn()
    row = _fetchone('SELECT * FROM records WHERE id=?', (record_id,))
    r = to_dict(row)
    if r:
        if r.get('custom_values'):
            try:
                r['custom_values'] = json.loads(r['custom_values'])
            except Exception:
                r['custom_values'] = {}
        else:
            r['custom_values'] = {}
        r['beneficiaries'] = int(r.get('beneficiaries') or 0)
    return r


def save_record(data, user_id=None):
    """Insert or update record."""
    conn = get_conn()
    rid = data.get('id') or uid('rec')
    custom_values = data.get('customValues', {}) or {}
    now = now_iso()
    existing = _fetchone('SELECT id FROM records WHERE id=?', (rid,))
    if existing:
        _exec('''
            UPDATE records SET
                expert_name=?, role_id=?, role_name=?, org=?,
                province_id=?, province_name=?,
                county_id=?, county_name=?,
                district_id=?, district_name=?,
                village=?, service_id=?, service_name=?,
                service_date=?, beneficiaries=?, description=?, evidence=?,
                custom_values=?, updated_at=?
            WHERE id=?
        ''', (
            data.get('expertName', ''),
            data.get('roleId', ''),
            data.get('roleName', ''),
            data.get('org', ''),
            data.get('provinceId', ''),
            data.get('provinceName', ''),
            data.get('countyId', ''),
            data.get('countyName', ''),
            data.get('districtId', ''),
            data.get('districtName', ''),
            data.get('village', ''),
            data.get('serviceId', ''),
            data.get('serviceName', ''),
            data.get('serviceDate', ''),
            int(data.get('beneficiaries') or 0),
            data.get('description', ''),
            data.get('evidence', ''),
            json.dumps(custom_values, ensure_ascii=False),
            now,
            rid
        ))
    else:
        _exec('''
            INSERT INTO records(
                id, expert_name, role_id, role_name, org,
                province_id, province_name,
                county_id, county_name,
                district_id, district_name,
                village, service_id, service_name,
                service_date, beneficiaries, description, evidence,
                custom_values, created_by_user_id, updated_at, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            rid,
            data.get('expertName', ''),
            data.get('roleId', ''),
            data.get('roleName', ''),
            data.get('org', ''),
            data.get('provinceId', ''),
            data.get('provinceName', ''),
            data.get('countyId', ''),
            data.get('countyName', ''),
            data.get('districtId', ''),
            data.get('districtName', ''),
            data.get('village', ''),
            data.get('serviceId', ''),
            data.get('serviceName', ''),
            data.get('serviceDate', ''),
            int(data.get('beneficiaries') or 0),
            data.get('description', ''),
            data.get('evidence', ''),
            json.dumps(custom_values, ensure_ascii=False),
            user_id,
            now, now
        ))
    return rid


def delete_record(rid):
    conn = get_conn()
    _exec('DELETE FROM records WHERE id=?', (rid,))


# ----- Announcements -----
def list_announcements():
    conn = get_conn()
    return rows_to_dicts(_fetchall('SELECT * FROM announcements ORDER BY created_at DESC'))


def add_announcement(text):
    aid = uid('an')
    conn = get_conn()
    _exec('INSERT INTO announcements(id, text, active) VALUES (?,?,1)', (aid, text))
    return aid


def delete_announcement(aid):
    conn = get_conn()
    _exec('DELETE FROM announcements WHERE id=?', (aid,))


# ----- Custom Fields -----
def list_custom_fields():
    conn = get_conn()
    return rows_to_dicts(_fetchall('SELECT * FROM custom_fields ORDER BY created_at'))


def add_custom_field(label, field_type='text', scope='all'):
    fid = uid('cf')
    conn = get_conn()
    _exec('INSERT INTO custom_fields(id, label, type, scope, active) VALUES (?,?,?,?,1)',
                 (fid, label, field_type, scope))
    return fid


def update_custom_field(fid, label=None, active=None):
    conn = get_conn()
    if label is not None:
        _exec('UPDATE custom_fields SET label=? WHERE id=?', (label, fid))
    if active is not None:
        _exec('UPDATE custom_fields SET active=? WHERE id=?', (1 if active else 0, fid))


def delete_custom_field(fid):
    conn = get_conn()
    _exec('DELETE FROM custom_fields WHERE id=?', (fid,))


# ----- Settings -----
def get_all_settings():
    conn = get_conn()
    rows = _fetchall('SELECT key, value FROM settings')
    s = {}
    for r in rows:
        s[r['key']] = r['value']
    # Defaults
    s.setdefault('showLoginDemoNotice', '1')
    s.setdefault('evidenceEnabled', '1')
    s['showLoginDemoNotice'] = s['showLoginDemoNotice'] == '1' or s['showLoginDemoNotice'] is True
    s['evidenceEnabled'] = s['evidenceEnabled'] == '1' or s['evidenceEnabled'] is True
    return s


def set_settings(updates):
    for k, v in updates.items():
        if isinstance(v, bool):
            v = '1' if v else '0'
        # Upsert: update if exists, insert if not
        if _fetchone('SELECT key FROM settings WHERE key=?', (k,)):
            _exec('UPDATE settings SET value=? WHERE key=?', (v, k))
        else:
            _exec('INSERT INTO settings(key, value) VALUES (?,?)', (k, v))


# ----- Core fields -----
def get_core_fields():
    conn = get_conn()
    rows = _fetchall('SELECT * FROM core_fields ORDER BY field_key')
    return rows_to_dicts(rows)


def set_core_field(field_key, label, visible):
    vis = 1 if visible else 0
    if _fetchone('SELECT field_key FROM core_fields WHERE field_key=?', (field_key,)):
        _exec('UPDATE core_fields SET label=?, visible=? WHERE field_key=?', (label, vis, field_key))
    else:
        _exec('INSERT INTO core_fields(field_key, label, visible) VALUES (?,?,?)', (field_key, label, vis))


# ----- Geo Catalog -----
def list_geo_catalog():
    conn = get_conn()
    return rows_to_dicts(_fetchall('SELECT * FROM geo_catalog ORDER BY province_name, county_name, village_name'))


def add_geo_entries(entries):
    """entries: list of dicts with keys province_name, county_name, section_name (optional), district_name (optional), village_name."""
    for e in entries:
        # Check if entry already exists before inserting
        existing = _fetchone(
            'SELECT id FROM geo_catalog WHERE province_name=? AND county_name=? AND village_name=? '
            'AND COALESCE(section_name,\'\')=? AND COALESCE(district_name,\'\')=?',
            (e['province_name'], e['county_name'], e['village_name'],
             e.get('section_name') or '', e.get('district_name') or '')
        )
        if not existing:
            gid = uid('geo')
            _exec(
                'INSERT INTO geo_catalog(id, province_name, county_name, section_name, district_name, village_name) VALUES (?,?,?,?,?,?)',
                (gid, e['province_name'], e['county_name'], e.get('section_name') or '', e.get('district_name') or '', e['village_name'])
            )


def clear_geo_catalog():
    conn = get_conn()
    _exec('DELETE FROM geo_catalog')


# ----- Login announcements & banners -----
def list_login_announcements(active_only=False):
    conn = get_conn()
    sql = 'SELECT * FROM login_announcements'
    if active_only:
        sql += ' WHERE active=1'
    sql += ' ORDER BY sort_order, created_at DESC'
    return rows_to_dicts(_fetchall(sql))


def add_login_announcement(text, festive=False, sort_order=0):
    aid = uid('la')
    conn = get_conn()
    _exec(
        'INSERT INTO login_announcements(id, text, festive, active, sort_order) VALUES (?,?,?,1,?)',
        (aid, text, 1 if festive else 0, sort_order)
    )
    return aid


def update_login_announcement(aid, text=None, festive=None, active=None, sort_order=None):
    conn = get_conn()
    if text is not None:
        _exec('UPDATE login_announcements SET text=? WHERE id=?', (text, aid))
    if festive is not None:
        _exec('UPDATE login_announcements SET festive=? WHERE id=?', (1 if festive else 0, aid))
    if active is not None:
        _exec('UPDATE login_announcements SET active=? WHERE id=?', (1 if active else 0, aid))
    if sort_order is not None:
        _exec('UPDATE login_announcements SET sort_order=? WHERE id=?', (sort_order, aid))


def delete_login_announcement(aid):
    conn = get_conn()
    _exec('DELETE FROM login_announcements WHERE id=?', (aid,))


def list_login_banners(active_only=False):
    conn = get_conn()
    sql = 'SELECT * FROM login_banners'
    if active_only:
        sql += ' WHERE active=1'
    sql += ' ORDER BY sort_order, created_at DESC'
    return rows_to_dicts(_fetchall(sql))


def add_login_banner(image_data, image_mime='image/jpeg', link_url='', title='', sort_order=0):
    bid = uid('lb')
    conn = get_conn()
    _exec(
        'INSERT INTO login_banners(id, image_data, image_mime, link_url, title, active, sort_order) '
        'VALUES (?,?,?,?,?,1,?)',
        (bid, image_data, image_mime, link_url, title, sort_order)
    )
    return bid


def update_login_banner(bid, active=None, sort_order=None, link_url=None, title=None):
    conn = get_conn()
    if active is not None:
        _exec('UPDATE login_banners SET active=? WHERE id=?', (1 if active else 0, bid))
    if sort_order is not None:
        _exec('UPDATE login_banners SET sort_order=? WHERE id=?', (sort_order, bid))
    if link_url is not None:
        _exec('UPDATE login_banners SET link_url=? WHERE id=?', (link_url, bid))
    if title is not None:
        _exec('UPDATE login_banners SET title=? WHERE id=?', (title, bid))


def delete_login_banner(bid):
    conn = get_conn()
    _exec('DELETE FROM login_banners WHERE id=?', (bid,))


# ----- Backup / Restore -----
def export_all_data():
    """Return a dict with all data for JSON backup."""
    return {
        'exported_at': now_iso(),
        'roles': list_roles(),
        'services': list_services(),
        'provinces': list_provinces(),
        'records': list_records(),
        'announcements': list_announcements(),
        'customFields': list_custom_fields(),
        'coreFields': get_core_fields(),
        'settings': get_all_settings(),
        'geoCatalog': list_geo_catalog(),
        'users': list_users(),
    }


# ===== PLAN MANAGEMENT SYSTEM (سامانه طرح‌های پویا) =====

# ----- Plans CRUD -----
def list_plans(active_only=False, search=''):
    """List all plans with their allowed status categories."""
    sql = 'SELECT * FROM plans'
    conditions = []
    params = []
    if active_only:
        conditions.append('active=1')
    if search:
        conditions.append('(name LIKE ? OR description LIKE ?)')
        params.extend([f'%{search}%', f'%{search}%'])
    if conditions:
        sql += ' WHERE ' + ' AND '.join(conditions)
    sql += ' ORDER BY sort_order, created_at'
    plans = rows_to_dicts(_fetchall(sql, tuple(params) if params else None))
    # Attach allowed statuses and field count
    for p in plans:
        p['allowed_statuses'] = [r['status_category'] for r in rows_to_dicts(_fetchall(
            'SELECT status_category FROM plan_status_allowed WHERE plan_id=?', (p['id'],)))]
        p['field_count'] = _fetchval(
            'SELECT COUNT(*) FROM plan_fields WHERE plan_id=? AND active=1', (p['id'],))
        p['record_count'] = _fetchval(
            'SELECT COUNT(*) FROM plan_records WHERE plan_id=?', (p['id'],))
    return plans


def get_plan(pid):
    """Get a single plan with its allowed statuses."""
    p = _fetchone('SELECT * FROM plans WHERE id=?', (pid,))
    if not p:
        return None
    p['allowed_statuses'] = [r['status_category'] for r in rows_to_dicts(_fetchall(
        'SELECT status_category FROM plan_status_allowed WHERE plan_id=?', (pid,)))]
    return p


def add_plan(name, description='', allowed_statuses=None, allow_duplicate=0, sort_order=0, created_by=None):
    """Create a new plan."""
    pid = uid('plan')
    _exec(
        'INSERT INTO plans(id, name, description, active, allow_duplicate, sort_order, created_by) '
        'VALUES (?,?,?,?,?,?,?)',
        (pid, name, description, 1, allow_duplicate, sort_order, created_by)
    )
    if allowed_statuses:
        _set_plan_statuses(pid, allowed_statuses)
    else:
        _set_plan_statuses(pid, ['done', 'in_progress', 'capacity'])
    return pid


def update_plan(pid, name=None, description=None, active=None, allow_duplicate=None,
                sort_order=None, allowed_statuses=None):
    """Update a plan. Only provided fields are updated."""
    parts = []
    params = []
    if name is not None:
        parts.append('name=?')
        params.append(name)
    if description is not None:
        parts.append('description=?')
        params.append(description)
    if active is not None:
        parts.append('active=?')
        params.append(active)
    if allow_duplicate is not None:
        parts.append('allow_duplicate=?')
        params.append(allow_duplicate)
    if sort_order is not None:
        parts.append('sort_order=?')
        params.append(sort_order)
    if parts:
        parts.append('updated_at=CURRENT_TIMESTAMP')
        params.append(pid)
        _exec(f'UPDATE plans SET {",".join(parts)} WHERE id=?', tuple(params))
    if allowed_statuses is not None:
        _set_plan_statuses(pid, allowed_statuses)


def _set_plan_statuses(pid, statuses):
    """Replace the allowed status categories for a plan."""
    _exec('DELETE FROM plan_status_allowed WHERE plan_id=?', (pid,))
    for s in statuses:
        sid = uid('psa')
        _exec('INSERT INTO plan_status_allowed(id, plan_id, status_category) VALUES (?,?,?)',
              (sid, pid, s))


def delete_plan(pid):
    """Soft-delete a plan (deactivate). Records are kept but excluded from stats."""
    _exec('UPDATE plans SET active=0, updated_at=CURRENT_TIMESTAMP WHERE id=?', (pid,))


def hard_delete_plan(pid):
    """Hard delete a plan and ALL its data (records, fields, history)."""
    _exec('DELETE FROM plan_status_history WHERE plan_record_id IN (SELECT id FROM plan_records WHERE plan_id=?)', (pid,))
    _exec('DELETE FROM plan_records WHERE plan_id=?', (pid,))
    _exec('DELETE FROM plan_fields WHERE plan_id=?', (pid,))
    _exec('DELETE FROM plan_status_allowed WHERE plan_id=?', (pid,))
    _exec('DELETE FROM plans WHERE id=?', (pid,))


# ----- Plan Fields CRUD -----
def list_plan_fields(pid, active_only=True):
    """List all fields for a plan."""
    sql = 'SELECT * FROM plan_fields WHERE plan_id=?'
    if active_only:
        sql += ' AND active=1'
    sql += ' ORDER BY sort_order, created_at'
    return rows_to_dicts(_fetchall(sql, (pid,)))


def get_plan_field(fid):
    return _fetchone('SELECT * FROM plan_fields WHERE id=?', (fid,))


def add_plan_field(pid, field_key, label, field_type='text', required=0, options=None,
                   help_text='', sort_order=0):
    fid = uid('pf')
    import json as _json
    opts_json = _json.dumps(options, ensure_ascii=False) if options else None
    _exec(
        'INSERT INTO plan_fields(id, plan_id, field_key, label, type, required, options, '
        'help_text, sort_order, active) VALUES (?,?,?,?,?,?,?,?,?,1)',
        (fid, pid, field_key, label, field_type, required, opts_json, help_text, sort_order)
    )
    return fid


def update_plan_field(fid, field_key=None, label=None, field_type=None, required=None,
                      options=None, help_text=None, sort_order=None, active=None):
    parts = []
    params = []
    if field_key is not None: parts.append('field_key=?'); params.append(field_key)
    if label is not None: parts.append('label=?'); params.append(label)
    if field_type is not None: parts.append('type=?'); params.append(field_type)
    if required is not None: parts.append('required=?'); params.append(required)
    if options is not None:
        import json as _json
        parts.append('options=?')
        params.append(_json.dumps(options, ensure_ascii=False) if options else None)
    if help_text is not None: parts.append('help_text=?'); params.append(help_text)
    if sort_order is not None: parts.append('sort_order=?'); params.append(sort_order)
    if active is not None: parts.append('active=?'); params.append(active)
    if parts:
        parts.append('updated_at=CURRENT_TIMESTAMP')
        params.append(fid)
        _exec(f'UPDATE plan_fields SET {",".join(parts)} WHERE id=?', tuple(params))


def delete_plan_field(fid):
    """Soft-delete a field if it has data, hard delete if not."""
    _exec('UPDATE plan_fields SET active=0, updated_at=CURRENT_TIMESTAMP WHERE id=?', (fid,))


# ----- Plan Records -----
def list_plan_records(filters=None):
    """List plan records with optional filters. Supports comma-separated multi-values."""
    sql = ('SELECT pr.*, p.name as plan_name FROM plan_records pr '
           'LEFT JOIN plans p ON p.id=pr.plan_id WHERE 1=1')
    conditions = []
    params = []
    if filters:
        if filters.get('plan_id'):
            ids = [v.strip() for v in filters['plan_id'].split(',') if v.strip()]
            if ids:
                placeholders = ','.join(['?' for _ in ids])
                conditions.append(f'pr.plan_id IN ({placeholders})')
                params.extend(ids)
        if filters.get('village'):
            conditions.append('pr.village LIKE ?')
            params.append(f'%{filters["village"]}%')
        if filters.get('province_id'):
            ids = [v.strip() for v in filters['province_id'].split(',') if v.strip()]
            if ids:
                placeholders = ','.join(['?' for _ in ids])
                conditions.append(f'pr.province_id IN ({placeholders})')
                params.extend(ids)
        if filters.get('county_id'):
            ids = [v.strip() for v in filters['county_id'].split(',') if v.strip()]
            if ids:
                placeholders = ','.join(['?' for _ in ids])
                conditions.append(f'pr.county_id IN ({placeholders})')
                params.extend(ids)
        if filters.get('section_id'):
            ids = [v.strip() for v in filters['section_id'].split(',') if v.strip()]
            if ids:
                placeholders = ','.join(['?' for _ in ids])
                conditions.append(f'pr.section_id IN ({placeholders})')
                params.extend(ids)
        if filters.get('status_category'):
            conditions.append('pr.status_category=?')
            params.append(filters['status_category'])
    if conditions:
        sql += ' AND ' + ' AND '.join(conditions)
    sql += ' ORDER BY pr.created_at DESC'
    return rows_to_dicts(_fetchall(sql, tuple(params) if params else None))


def get_plan_record(rid):
    return _fetchone('SELECT * FROM plan_records WHERE id=?', (rid,))


def find_plan_record(plan_id, village, province_id='', county_id=''):
    """Find an existing record for this plan+village combination."""
    pid = province_id or None
    cid = county_id or None
    sql = 'SELECT * FROM plan_records WHERE plan_id=? AND village=?'
    params = [plan_id, village]
    if pid:
        sql += ' AND province_id=?'
        params.append(pid)
    else:
        sql += ' AND province_id IS NULL'
    if cid:
        sql += ' AND county_id=?'
        params.append(cid)
    else:
        sql += ' AND county_id IS NULL'
    return _fetchone(sql, tuple(params))


def add_plan_record(plan_id, village, status_category, field_values=None, province_id='',
                    county_id='', section_id='', district_id='', expert_name='', role_id='', org='',
                    service_date='', description='', created_by=''):
    """Create a new plan record. Raises if duplicate exists."""
    existing = find_plan_record(plan_id, village, province_id, county_id)
    if existing:
        plan = get_plan(plan_id)
        if plan and not plan.get('allow_duplicate'):
            raise ValueError('برای این روستا قبلاً طرح ثبت شده است. می‌توانید وضعیت آن را تغییر دهید.')
    rid = uid('pr')
    import json as _json
    fv_json = _json.dumps(field_values, ensure_ascii=False) if field_values else None
    _exec(
        'INSERT INTO plan_records(id, plan_id, province_id, county_id, section_id, district_id, village, '
        'status_category, field_values, expert_name, role_id, org, service_date, description, created_by) '
        'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
        (rid, plan_id, province_id or None, county_id or None, section_id or None, district_id or None, village,
         status_category, fv_json, expert_name, role_id, org, service_date, description, created_by)
    )
    # Log initial status
    _add_status_history(rid, None, status_category, created_by, 'ثبت اولیه')
    return rid


def update_plan_record_status(rid, new_status, changed_by='', note=''):
    """Change the status of a plan record. Logs to history."""
    record = get_plan_record(rid)
    if not record:
        raise ValueError('رکورد یافت نشد.')
    old_status = record.get('status_category')
    if old_status == new_status:
        return
    _exec('UPDATE plan_records SET status_category=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
          (new_status, rid))
    _add_status_history(rid, old_status, new_status, changed_by, note)


def update_plan_record(rid, field_values=None, expert_name=None, org=None,
                       service_date=None, description=None):
    """Update a plan record's field values and metadata."""
    parts = []
    params = []
    if field_values is not None:
        import json as _json
        parts.append('field_values=?')
        params.append(_json.dumps(field_values, ensure_ascii=False))
    if expert_name is not None: parts.append('expert_name=?'); params.append(expert_name)
    if org is not None: parts.append('org=?'); params.append(org)
    if service_date is not None: parts.append('service_date=?'); params.append(service_date)
    if description is not None: parts.append('description=?'); params.append(description)
    if parts:
        parts.append('updated_at=CURRENT_TIMESTAMP')
        params.append(rid)
        _exec(f'UPDATE plan_records SET {",".join(parts)} WHERE id=?', tuple(params))


def delete_plan_record(rid):
    _exec('DELETE FROM plan_records WHERE id=?', (rid,))


# ----- Status History -----
def _add_status_history(rid, old_status, new_status, changed_by='', note=''):
    hid = uid('psh')
    _exec(
        'INSERT INTO plan_status_history(id, plan_record_id, old_status, new_status, '
        'changed_by, note) VALUES (?,?,?,?,?,?)',
        (hid, rid, old_status, new_status, changed_by, note)
    )


def get_status_history(rid):
    return rows_to_dicts(_fetchall(
        'SELECT * FROM plan_status_history WHERE plan_record_id=? ORDER BY changed_at DESC',
        (rid,)
    ))


# ----- Plan Statistics -----
def get_plan_stats():
    """Get summary statistics for the admin dashboard.
    Only counts records from ACTIVE plans."""
    total_plans = _fetchval('SELECT COUNT(*) FROM plans') or 0
    active_plans = _fetchval('SELECT COUNT(*) FROM plans WHERE active=1') or 0
    # Only count records from ACTIVE plans
    total_records = _fetchval('SELECT COUNT(*) FROM plan_records WHERE plan_id IN (SELECT id FROM plans WHERE active=1)') or 0
    done_count = _fetchval("SELECT COUNT(*) FROM plan_records WHERE status_category='done' AND plan_id IN (SELECT id FROM plans WHERE active=1)") or 0
    in_progress_count = _fetchval("SELECT COUNT(*) FROM plan_records WHERE status_category='in_progress' AND plan_id IN (SELECT id FROM plans WHERE active=1)") or 0
    capacity_count = _fetchval("SELECT COUNT(*) FROM plan_records WHERE status_category='capacity' AND plan_id IN (SELECT id FROM plans WHERE active=1)") or 0
    villages_count = _fetchval('SELECT COUNT(DISTINCT village) FROM plan_records WHERE plan_id IN (SELECT id FROM plans WHERE active=1)') or 0
    return {
        'total_plans': total_plans,
        'active_plans': active_plans,
        'inactive_plans': total_plans - active_plans,
        'total_records': total_records,
        'done': done_count,
        'in_progress': in_progress_count,
        'capacity': capacity_count,
        'villages_count': villages_count,
    }


# ===== PASSWORD RESET REQUESTS =====
def create_reset_request(user_id, user_name, username, province_id, county_id, user_role):
    """Create a password reset request."""
    rid = uid('rr')
    _exec(
        'INSERT INTO password_reset_requests(id, user_id, user_name, username, '
        'province_id, county_id, user_role, status) VALUES (?,?,?,?,?,?,?,?)',
        (rid, user_id, user_name, username, province_id or None, county_id or None, user_role, 'pending')
    )
    return rid


def list_reset_requests(status='pending', admin_role='national', admin_province_id=None):
    """List reset requests. Provincial admin sees their province's requests."""
    sql = 'SELECT * FROM password_reset_requests WHERE status=?'
    params = [status]
    if admin_role == 'provincial' and admin_province_id:
        sql += ' AND province_id=?'
        params.append(admin_province_id)
    sql += ' ORDER BY created_at DESC'
    return rows_to_dicts(_fetchall(sql, tuple(params)))


def approve_reset_request(rid, reviewed_by):
    """Approve request — reset password to 123456789."""
    req = _fetchone('SELECT * FROM password_reset_requests WHERE id=?', (rid,))
    if not req:
        raise ValueError('درخواست یافت نشد.')
    # Reset the user's password to default
    user = _fetchone('SELECT * FROM users WHERE username=?', (req['username'],))
    if user:
        _exec('UPDATE users SET password_hash=? WHERE id=?',
              (generate_password_hash('123456789'), user['id']))
    # Mark request as approved
    _exec('UPDATE password_reset_requests SET status=?, reviewed_by=?, reviewed_at=CURRENT_TIMESTAMP WHERE id=?',
          ('approved', reviewed_by, rid))


def reject_reset_request(rid, reviewed_by):
    """Reject request."""
    _exec('UPDATE password_reset_requests SET status=?, reviewed_by=?, reviewed_at=CURRENT_TIMESTAMP WHERE id=?',
          ('rejected', reviewed_by, rid))

# ===== MESSAGING SYSTEM (پیام‌رسانی) =====
def send_message(sender_id, sender_name, sender_role, target_role, subject, body,
                 target_province_id=None, target_county_id=None):
    mid = uid('msg')
    _exec(
        'INSERT INTO messages(id, sender_id, sender_name, sender_role, target_role, '
        'target_province_id, target_county_id, subject, body) VALUES (?,?,?,?,?,?,?,?,?)',
        (mid, sender_id, sender_name, sender_role, target_role,
         target_province_id or None, target_county_id or None, subject, body)
    )
    return mid


def list_inbox(user_id, role, province_id=None, county_id=None):
    """Get messages visible to this user based on role and scope."""
    sql = ('SELECT * FROM messages WHERE target_role=? AND '
           '(target_province_id IS NULL OR target_province_id=? OR target_province_id=?) '
           'AND (target_county_id IS NULL OR target_county_id=? OR target_county_id=?) '
           'ORDER BY created_at DESC')
    params = (role, province_id or '', province_id or '', county_id or '', county_id or '')
    return rows_to_dicts(_fetchall(sql, params))


def list_sent(user_id):
    """Get messages sent by this user."""
    return rows_to_dicts(_fetchall(
        'SELECT * FROM messages WHERE sender_id=? ORDER BY created_at DESC', (user_id,)))


def mark_message_read(mid):
    _exec('UPDATE messages SET is_read=1 WHERE id=?', (mid,))


def delete_message(mid):
    _exec('DELETE FROM messages WHERE id=?', (mid,))


def get_unread_count(user_id, role, province_id=None, county_id=None):
    msgs = list_inbox(user_id, role, province_id, county_id)
    return sum(1 for m in msgs if not m.get('is_read'))
