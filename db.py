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


def get_conn():
    """Return a per-thread connection.
    - PostgreSQL: psycopg2 connection with RealDictCursor
    - SQLite: sqlite3 connection with Row factory
    """
    if not hasattr(_local, 'conn'):
        if IS_POSTGRES:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            _local.conn = psycopg2.connect(DATABASE_URL)
            _local.conn.autocommit = True
            _local.conn.cursor_factory = RealDictCursor
        else:
            import sqlite3
            _local.conn = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)
            _local.conn.row_factory = sqlite3.Row
            _local.conn.execute('PRAGMA journal_mode=WAL;')
            _local.conn.execute('PRAGMA foreign_keys=ON;')
            _local.conn.execute('PRAGMA busy_timeout=5000;')
    return _local.conn


def _convert_sql(sql):
    """Convert SQLite-style ? placeholders to PostgreSQL %s placeholders."""
    if IS_POSTGRES:
        return sql.replace('?', '%s')
    return sql


def _exec(sql, params=None):
    """Execute a single SQL statement. Returns cursor."""
    conn = get_conn()
    sql = _convert_sql(sql)
    if IS_POSTGRES:
        cur = conn.cursor()
        cur.execute(sql, params or ())
        return cur
    else:
        return conn.execute(sql, params or ())


def _execmany(sql, seq_of_params):
    """Execute many. Returns cursor."""
    conn = get_conn()
    sql = _convert_sql(sql)
    if IS_POSTGRES:
        cur = conn.cursor()
        cur.executemany(sql, seq_of_params)
        return cur
    else:
        return conn.executemany(sql, seq_of_params)


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
    _seed_defaults()
    db_info = f'PostgreSQL: {DATABASE_URL[:50]}...' if IS_POSTGRES else f'SQLite at {DB_PATH}'
    print(f'[db] initialized ({db_info})')


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
    """entries: list of dicts with keys province_name, county_name, district_name (optional), village_name."""
    for e in entries:
        # Check if entry already exists before inserting
        existing = _fetchone(
            'SELECT id FROM geo_catalog WHERE province_name=? AND county_name=? AND village_name=?',
            (e['province_name'], e['county_name'], e['village_name'])
        )
        if not existing:
            gid = uid('geo')
            _exec(
                'INSERT INTO geo_catalog(id, province_name, county_name, district_name, village_name) VALUES (?,?,?,?,?)',
                (gid, e['province_name'], e['county_name'], e.get('district_name') or '', e['village_name'])
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
