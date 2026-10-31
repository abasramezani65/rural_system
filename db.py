"""Database helpers for the Rural Services System."""
import os
import sqlite3
import json
import threading
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = os.environ.get('RURAL_DB_PATH', os.path.join(os.path.dirname(__file__), 'rural.db'))
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), 'schema.sql')

_local = threading.local()


def get_conn():
    """Return a per-thread connection. Sets row_factory to dict-like."""
    if not hasattr(_local, 'conn'):
        conn = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA journal_mode=WAL;')
        conn.execute('PRAGMA foreign_keys=ON;')
        conn.execute('PRAGMA busy_timeout=5000;')
        _local.conn = conn
    return _local.conn


def init_db():
    """Initialize the database schema and seed default data."""
    with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
        schema_sql = f.read()
    conn = get_conn()
    conn.executescript(schema_sql)
    _seed_defaults()
    print(f'[db] initialized at {DB_PATH}')


def _seed_defaults():
    """Seed default roles, services, settings, and admin user if empty."""
    conn = get_conn()
    # Roles
    if conn.execute('SELECT COUNT(*) FROM roles').fetchone()[0] == 0:
        conn.executemany(
            'INSERT OR IGNORE INTO roles(id, name, active) VALUES (?,?,?)',
            [('r1', 'کارشناس شهرستان', 1),
             ('r2', 'مسئول استانی', 1),
             ('r3', 'کارشناس کشوری', 1)]
        )
    # Services
    if conn.execute('SELECT COUNT(*) FROM services').fetchone()[0] == 0:
        conn.executemany(
            'INSERT OR IGNORE INTO services(id, name, active) VALUES (?,?,?)',
            [('s1', 'آبرسانی', 1),
             ('s2', 'اشتغال‌زایی', 1),
             ('s3', 'بهسازی راه', 1)]
        )
    # Provinces & counties - one default
    if conn.execute('SELECT COUNT(*) FROM provinces').fetchone()[0] == 0:
        conn.execute("INSERT OR IGNORE INTO provinces(id, name) VALUES ('p1','نمونه استان')")
        conn.execute("INSERT OR IGNORE INTO counties(id, province_id, name) VALUES ('c1','p1','نمونه شهرستان')")
    # Admin user
    row = conn.execute("SELECT id FROM users WHERE username='admin'").fetchone()
    if not row:
        conn.execute(
            "INSERT INTO users(id, name, username, password_hash, role, province_id, county_id, active) VALUES (?,?,?,?,?,?,?,?)",
            ('u_admin_default', 'مدیر سامانه', 'admin', generate_password_hash('admin12345'), 'national', None, None, 1)
        )
    else:
        # Ensure admin password is correct (in case of reseed)
        conn.execute(
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
        conn.execute('INSERT OR IGNORE INTO settings(key, value) VALUES (?,?)', (k, v))
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
        conn.execute('INSERT OR IGNORE INTO core_fields(field_key, label, visible) VALUES (?,?,?)',
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
    conn.execute('INSERT INTO sessions(token, user_id, expires_at) VALUES (?,?,?)',
                 (token, user_id, expires))
    return token


def get_session_user(token):
    if not token:
        return None
    conn = get_conn()
    row = conn.execute(
        'SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id '
        'WHERE s.token=? AND s.expires_at > datetime("now") AND u.active=1',
        (token,)
    ).fetchone()
    return to_dict(row)


def destroy_session(token):
    if not token:
        return
    conn = get_conn()
    conn.execute('DELETE FROM sessions WHERE token=?', (token,))


def cleanup_sessions():
    conn = get_conn()
    conn.execute('DELETE FROM sessions WHERE expires_at <= datetime("now")')


# ----- Users -----
def list_users():
    conn = get_conn()
    rows = conn.execute('SELECT id, name, username, role, province_id, county_id, active, created_at FROM users ORDER BY created_at').fetchall()
    return rows_to_dicts(rows)


def get_user_by_username(username):
    conn = get_conn()
    row = conn.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
    return to_dict(row)


def get_user(user_id):
    conn = get_conn()
    row = conn.execute('SELECT id, name, username, role, province_id, county_id, active FROM users WHERE id=?', (user_id,)).fetchone()
    return to_dict(row)


def create_user(name, username, password, role, province_id='', county_id=''):
    conn = get_conn()
    user_id = uid('u')
    pw_hash = generate_password_hash(password)
    conn.execute(
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
        conn.execute(
            'UPDATE users SET name=?, username=?, password_hash=?, role=?, province_id=?, county_id=?, active=? WHERE id=?',
            (name, username, pw_hash, role, pid, cid, active, user_id)
        )
    else:
        conn.execute(
            'UPDATE users SET name=?, username=?, role=?, province_id=?, county_id=?, active=? WHERE id=?',
            (name, username, role, pid, cid, active, user_id)
        )


def delete_user(user_id):
    if user_id == 'u_admin_default':
        return False  # protect admin
    conn = get_conn()
    conn.execute('DELETE FROM users WHERE id=?', (user_id,))
    return True


def toggle_user(user_id, active):
    conn = get_conn()
    conn.execute('UPDATE users SET active=? WHERE id=?', (1 if active else 0, user_id))


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
    return rows_to_dicts(conn.execute(sql).fetchall())


def add_role(name):
    rid = uid('r')
    conn = get_conn()
    conn.execute('INSERT INTO roles(id, name, active) VALUES (?,?,1)', (rid, name))
    return rid


def update_role(rid, name=None, active=None):
    conn = get_conn()
    if name is not None:
        conn.execute('UPDATE roles SET name=? WHERE id=?', (name, rid))
    if active is not None:
        conn.execute('UPDATE roles SET active=? WHERE id=?', (1 if active else 0, rid))


def delete_role(rid):
    conn = get_conn()
    conn.execute('DELETE FROM roles WHERE id=?', (rid,))


# ----- Services -----
def list_services(active_only=False):
    conn = get_conn()
    sql = 'SELECT * FROM services'
    if active_only:
        sql += ' WHERE active=1'
    sql += ' ORDER BY created_at'
    return rows_to_dicts(conn.execute(sql).fetchall())


def add_service(name):
    sid = uid('s')
    conn = get_conn()
    conn.execute('INSERT INTO services(id, name, active) VALUES (?,?,1)', (sid, name))
    return sid


def update_service(sid, name=None, active=None):
    conn = get_conn()
    if name is not None:
        conn.execute('UPDATE services SET name=? WHERE id=?', (name, sid))
    if active is not None:
        conn.execute('UPDATE services SET active=? WHERE id=?', (1 if active else 0, sid))


def delete_service(sid):
    conn = get_conn()
    conn.execute('DELETE FROM services WHERE id=?', (sid,))


# ----- Provinces & Counties -----
def list_provinces():
    conn = get_conn()
    rows = conn.execute('SELECT * FROM provinces ORDER BY name').fetchall()
    provinces = rows_to_dicts(rows)
    for p in provinces:
        counties = conn.execute('SELECT * FROM counties WHERE province_id=? ORDER BY name', (p['id'],)).fetchall()
        p['counties'] = rows_to_dicts(counties)
    return provinces


def add_province(name):
    pid = uid('p')
    conn = get_conn()
    conn.execute('INSERT INTO provinces(id, name) VALUES (?,?)', (pid, name))
    return pid


def add_county(province_id, name):
    cid = uid('c')
    conn = get_conn()
    conn.execute('INSERT INTO counties(id, province_id, name) VALUES (?,?,?)', (cid, province_id, name))
    return cid


def delete_province(pid):
    conn = get_conn()
    conn.execute('DELETE FROM provinces WHERE id=?', (pid,))


def delete_county(cid):
    conn = get_conn()
    conn.execute('DELETE FROM counties WHERE id=?', (cid,))


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
    rows = conn.execute(sql, params).fetchall()
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
    row = conn.execute('SELECT * FROM records WHERE id=?', (record_id,)).fetchone()
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
    existing = conn.execute('SELECT id FROM records WHERE id=?', (rid,)).fetchone()
    if existing:
        conn.execute('''
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
        conn.execute('''
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
    conn.execute('DELETE FROM records WHERE id=?', (rid,))


# ----- Announcements -----
def list_announcements():
    conn = get_conn()
    return rows_to_dicts(conn.execute('SELECT * FROM announcements ORDER BY created_at DESC').fetchall())


def add_announcement(text):
    aid = uid('an')
    conn = get_conn()
    conn.execute('INSERT INTO announcements(id, text, active) VALUES (?,?,1)', (aid, text))
    return aid


def delete_announcement(aid):
    conn = get_conn()
    conn.execute('DELETE FROM announcements WHERE id=?', (aid,))


# ----- Custom Fields -----
def list_custom_fields():
    conn = get_conn()
    return rows_to_dicts(conn.execute('SELECT * FROM custom_fields ORDER BY created_at').fetchall())


def add_custom_field(label, field_type='text', scope='all'):
    fid = uid('cf')
    conn = get_conn()
    conn.execute('INSERT INTO custom_fields(id, label, type, scope, active) VALUES (?,?,?,?,1)',
                 (fid, label, field_type, scope))
    return fid


def update_custom_field(fid, label=None, active=None):
    conn = get_conn()
    if label is not None:
        conn.execute('UPDATE custom_fields SET label=? WHERE id=?', (label, fid))
    if active is not None:
        conn.execute('UPDATE custom_fields SET active=? WHERE id=?', (1 if active else 0, fid))


def delete_custom_field(fid):
    conn = get_conn()
    conn.execute('DELETE FROM custom_fields WHERE id=?', (fid,))


# ----- Settings -----
def get_all_settings():
    conn = get_conn()
    rows = conn.execute('SELECT key, value FROM settings').fetchall()
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
    conn = get_conn()
    for k, v in updates.items():
        if isinstance(v, bool):
            v = '1' if v else '0'
        conn.execute('INSERT OR REPLACE INTO settings(key, value) VALUES (?,?)', (k, v))


# ----- Core fields -----
def get_core_fields():
    conn = get_conn()
    rows = conn.execute('SELECT * FROM core_fields ORDER BY field_key').fetchall()
    return rows_to_dicts(rows)


def set_core_field(field_key, label, visible):
    conn = get_conn()
    conn.execute('INSERT OR REPLACE INTO core_fields(field_key, label, visible) VALUES (?,?,?)',
                 (field_key, label, 1 if visible else 0))


# ----- Geo Catalog -----
def list_geo_catalog():
    conn = get_conn()
    return rows_to_dicts(conn.execute('SELECT * FROM geo_catalog ORDER BY province_name, county_name, village_name').fetchall())


def add_geo_entries(entries):
    """entries: list of dicts with keys province_name, county_name, district_name (optional), village_name."""
    conn = get_conn()
    for e in entries:
        gid = uid('geo')
        conn.execute(
            'INSERT OR IGNORE INTO geo_catalog(id, province_name, county_name, district_name, village_name) VALUES (?,?,?,?,?)',
            (gid, e['province_name'], e['county_name'], e.get('district_name') or '', e['village_name'])
        )


def clear_geo_catalog():
    conn = get_conn()
    conn.execute('DELETE FROM geo_catalog')


# ----- Login demo box items -----
def list_login_demo_items(active_only=False):
    conn = get_conn()
    sql = 'SELECT * FROM login_demo_items'
    if active_only:
        sql += ' WHERE active=1'
    sql += ' ORDER BY sort_order, created_at DESC'
    return rows_to_dicts(conn.execute(sql).fetchall())


def add_login_demo_item(title, content, sort_order=0):
    did = uid('ldi')
    conn = get_conn()
    conn.execute(
        'INSERT INTO login_demo_items(id, title, content, active, sort_order) VALUES (?,?,?,?,1,?)',
        (did, title, content, sort_order)
    )
    return did


def update_login_demo_item(did, title=None, content=None, active=None, sort_order=None):
    conn = get_conn()
    if title is not None:
        conn.execute('UPDATE login_demo_items SET title=? WHERE id=?', (title, did))
    if content is not None:
        conn.execute('UPDATE login_demo_items SET content=? WHERE id=?', (content, did))
    if active is not None:
        conn.execute('UPDATE login_demo_items SET active=? WHERE id=?', (1 if active else 0, did))
    if sort_order is not None:
        conn.execute('UPDATE login_demo_items SET sort_order=? WHERE id=?', (sort_order, did))


def delete_login_demo_item(did):
    conn = get_conn()
    conn.execute('DELETE FROM login_demo_items WHERE id=?', (did,))


# ----- Login announcements & banners -----
def list_login_announcements(active_only=False):
    conn = get_conn()
    sql = 'SELECT * FROM login_announcements'
    if active_only:
        sql += ' WHERE active=1'
    sql += ' ORDER BY sort_order, created_at DESC'
    return rows_to_dicts(conn.execute(sql).fetchall())


def add_login_announcement(text, festive=False, sort_order=0):
    aid = uid('la')
    conn = get_conn()
    conn.execute(
        'INSERT INTO login_announcements(id, text, festive, active, sort_order) VALUES (?,?,?,1,?)',
        (aid, text, 1 if festive else 0, sort_order)
    )
    return aid


def update_login_announcement(aid, text=None, festive=None, active=None, sort_order=None):
    conn = get_conn()
    if text is not None:
        conn.execute('UPDATE login_announcements SET text=? WHERE id=?', (text, aid))
    if festive is not None:
        conn.execute('UPDATE login_announcements SET festive=? WHERE id=?', (1 if festive else 0, aid))
    if active is not None:
        conn.execute('UPDATE login_announcements SET active=? WHERE id=?', (1 if active else 0, aid))
    if sort_order is not None:
        conn.execute('UPDATE login_announcements SET sort_order=? WHERE id=?', (sort_order, aid))


def delete_login_announcement(aid):
    conn = get_conn()
    conn.execute('DELETE FROM login_announcements WHERE id=?', (aid,))


def list_login_banners(active_only=False):
    conn = get_conn()
    sql = 'SELECT * FROM login_banners'
    if active_only:
        sql += ' WHERE active=1'
    sql += ' ORDER BY sort_order, created_at DESC'
    return rows_to_dicts(conn.execute(sql).fetchall())


def add_login_banner(image_data, image_mime='image/jpeg', link_url='', title='', sort_order=0):
    bid = uid('lb')
    conn = get_conn()
    conn.execute(
        'INSERT INTO login_banners(id, image_data, image_mime, link_url, title, active, sort_order) '
        'VALUES (?,?,?,?,?,1,?)',
        (bid, image_data, image_mime, link_url, title, sort_order)
    )
    return bid


def update_login_banner(bid, active=None, sort_order=None, link_url=None, title=None):
    conn = get_conn()
    if active is not None:
        conn.execute('UPDATE login_banners SET active=? WHERE id=?', (1 if active else 0, bid))
    if sort_order is not None:
        conn.execute('UPDATE login_banners SET sort_order=? WHERE id=?', (sort_order, bid))
    if link_url is not None:
        conn.execute('UPDATE login_banners SET link_url=? WHERE id=?', (link_url, bid))
    if title is not None:
        conn.execute('UPDATE login_banners SET title=? WHERE id=?', (title, bid))


def delete_login_banner(bid):
    conn = get_conn()
    conn.execute('DELETE FROM login_banners WHERE id=?', (bid,))


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
