"""Flask app for the Rural Services System.

Run with:
    python3 app.py
Open in browser: http://localhost:5050
"""
import os
import json
import csv
import io
from flask import Flask, request, jsonify, render_template, make_response, send_from_directory, abort

import db as DB

app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['JSON_AS_ASCII'] = False
app.config['SECRET_KEY'] = os.environ.get('RURAL_SECRET', 'change-this-in-production-please')
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 86400  # cache static files for 24 hours

# ----- Session cookie helper -----
COOKIE_NAME = 'rural_session'


def current_user():
    token = request.cookies.get(COOKIE_NAME)
    user = DB.get_session_user(token)
    return user


def require_auth():
    user = current_user()
    if not user:
        return None
    return user


def set_session_cookie(resp, token):
    resp.set_cookie(COOKIE_NAME, token, httponly=True, samesite='Lax', max_age=12*3600)
    return resp


def clear_session_cookie(resp):
    resp.set_cookie(COOKIE_NAME, '', expires=0)
    return resp


# ----- Routes: pages -----
@app.route('/')
def index():
    user = current_user()
    return render_template('index.html', logged_in=bool(user), user=user)


@app.route('/health')
def health():
    return jsonify({'status': 'ok'})


# ----- API: Auth -----
@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json(force=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    if not username or not password:
        return jsonify({'ok': False, 'error': 'نام کاربری و گذرواژه الزامی است.'}), 400
    user = DB.get_user_by_username(username)
    if not user or not DB.verify_password(user, password):
        return jsonify({'ok': False, 'error': 'نام کاربری یا گذرواژه نادرست است.'}), 401
    if not user.get('active'):
        return jsonify({'ok': False, 'error': 'این حساب غیرفعال است.'}), 403
    # Validate province/county scope still exists
    if user['role'] == 'provincial':
        if not DB.list_provinces() or not any(p['id'] == user['province_id'] for p in DB.list_provinces()):
            return jsonify({'ok': False, 'error': 'استان این حساب معتبر نیست.'}), 403
    elif user['role'] == 'county':
        provs = DB.list_provinces()
        if not any(p['id'] == user['province_id'] and any(c['id'] == user['county_id'] for c in p.get('counties', [])) for p in provs):
            return jsonify({'ok': False, 'error': 'شهرستان این حساب معتبر نیست.'}), 403
    token = DB.create_session(user['id'])
    # Check if user is using default password (must change)
    from werkzeug.security import check_password_hash
    must_change = check_password_hash(user['password_hash'], '123456789')
    resp = jsonify({'ok': True, 'user': {
        'id': user['id'], 'name': user['name'], 'username': user['username'],
        'role': user['role'], 'province_id': user['province_id'], 'county_id': user['county_id']
    }, 'must_change_password': must_change})
    return set_session_cookie(resp, token)


@app.route('/api/logout', methods=['POST'])
def api_logout():
    token = request.cookies.get(COOKIE_NAME)
    DB.destroy_session(token)
    resp = jsonify({'ok': True})
    return clear_session_cookie(resp)


@app.route('/api/me', methods=['GET'])
def api_me():
    user = current_user()
    if not user:
        return jsonify({'ok': False}), 401
    return jsonify({'ok': True, 'user': {
        'id': user['id'], 'name': user['name'], 'username': user['username'],
        'role': user['role'], 'province_id': user.get('province_id') or '', 'county_id': user.get('county_id') or ''
    }})


# ----- API: bootstrap (initial load) -----
@app.route('/api/state', methods=['GET'])
def api_state():
    """Return all data needed by frontend in one call."""
    user = current_user()
    if not user:
        # Allow reading of public settings + login announcements/banners + provinces for forgot password
        s = DB.get_all_settings()
        return jsonify({
            'authenticated': False,
            'settings': s,
            'provinces': DB.list_provinces(),
            'announcements': DB.list_announcements(),
            'loginAnnouncements': DB.list_login_announcements(active_only=True),
            'loginBanners': DB.list_login_banners(active_only=True),
        })
    # Filter records based on user scope
    filters = {}
    if user['role'] == 'provincial':
        filters['province_id'] = user['province_id']
    elif user['role'] == 'county':
        filters['province_id'] = user['province_id']
        filters['county_id'] = user['county_id']
    records = DB.list_records(filters)
    # Plan system data
    plan_filters = dict(filters)
    plan_records = DB.list_plan_records(plan_filters if plan_filters else None)
    return jsonify({
        'authenticated': True,
        'user': {
            'id': user['id'], 'name': user['name'], 'username': user['username'],
            'role': user['role'], 'province_id': user.get('province_id') or '', 'county_id': user.get('county_id') or ''
        },
        'roles': DB.list_roles(),
        'services': DB.list_services(),
        'provinces': DB.list_provinces(),
        'records': records,
        'announcements': DB.list_announcements(),
        'customFields': DB.list_custom_fields(),
        'coreFields': DB.get_core_fields(),
        'settings': DB.get_all_settings(),
        'geoCatalog': DB.list_geo_catalog()[:200],
        'users': DB.list_users() if user['role'] == 'national' else (DB.list_users_by_province(user['province_id']) if user['role'] == 'provincial' else []),
        'loginAnnouncements': DB.list_login_announcements(active_only=True),
        'loginBanners': DB.list_login_banners(active_only=True),
        'loginAnnouncementsAll': DB.list_login_announcements() if user['role'] == 'national' else [],
        'loginBannersAll': DB.list_login_banners() if user['role'] == 'national' else [],
        # Plan management data
        'plans': DB.list_plans() if user['role'] == 'national' else DB.list_plans(active_only=True),
        'planRecords': plan_records,
        'planStats': DB.get_plan_stats(),
    })


# ----- API: Login announcements -----
@app.route('/api/login-announcements', methods=['POST'])
def api_login_announcement_add():
    user = require_auth()
    if not user or user['role'] != 'national':
        return jsonify({'error': 'دسترسی غیرمجاز.'}), 403
    data = request.get_json(force=True) or {}
    text = (data.get('text') or '').strip()
    if not text:
        return jsonify({'error': 'متن اعلان الزامی است.'}), 400
    festive = bool(data.get('festive', False))
    sort_order = int(data.get('sort_order', 0) or 0)
    aid = DB.add_login_announcement(text, festive, sort_order)
    return jsonify({'ok': True, 'id': aid})


@app.route('/api/login-announcements/<aid>', methods=['POST'])
def api_login_announcement_update(aid):
    user = require_auth()
    if not user or user['role'] != 'national':
        return jsonify({'error': 'دسترسی غیرمجاز.'}), 403
    data = request.get_json(force=True) or {}
    DB.update_login_announcement(
        aid,
        text=data.get('text'),
        festive=data.get('festive'),
        active=data.get('active'),
        sort_order=data.get('sort_order')
    )
    return jsonify({'ok': True})


@app.route('/api/login-announcements/<aid>', methods=['DELETE'])
def api_login_announcement_delete(aid):
    user = require_auth()
    if not user or user['role'] != 'national':
        return jsonify({'error': 'دسترسی غیرمجاز.'}), 403
    DB.delete_login_announcement(aid)
    return jsonify({'ok': True})


# ----- API: Login banners -----
@app.route('/api/login-banners', methods=['POST'])
def api_login_banner_add():
    user = require_auth()
    if not user or user['role'] != 'national':
        return jsonify({'error': 'دسترسی غیرمجاز.'}), 403
    data = request.get_json(force=True) or {}
    image_data = data.get('image_data', '')
    mime = data.get('image_mime', 'image/jpeg')
    link_url = data.get('link_url', '')
    title = data.get('title', '')
    sort_order = int(data.get('sort_order', 0) or 0)
    if not image_data:
        return jsonify({'error': 'فایل تصویر الزامی است.'}), 400
    bid = DB.add_login_banner(image_data, mime, link_url, title, sort_order)
    return jsonify({'ok': True, 'id': bid})


@app.route('/api/login-banners/<bid>', methods=['POST'])
def api_login_banner_update(bid):
    user = require_auth()
    if not user or user['role'] != 'national':
        return jsonify({'error': 'دسترسی غیرمجاز.'}), 403
    data = request.get_json(force=True) or {}
    DB.update_login_banner(
        bid,
        active=data.get('active'),
        sort_order=data.get('sort_order'),
        link_url=data.get('link_url'),
        title=data.get('title')
    )
    return jsonify({'ok': True})


@app.route('/api/login-banners/<bid>', methods=['DELETE'])
def api_login_banner_delete(bid):
    user = require_auth()
    if not user or user['role'] != 'national':
        return jsonify({'error': 'دسترسی غیرمجاز.'}), 403
    DB.delete_login_banner(bid)
    return jsonify({'ok': True})


# ----- API: Roles -----
@app.route('/api/roles', methods=['GET'])
def api_roles():
    return jsonify({'roles': DB.list_roles()})


@app.route('/api/roles', methods=['POST'])
def api_role_add():
    user = require_auth()
    if not user or user['role'] != 'national':
        return jsonify({'error': 'دسترسی غیرمجاز.'}), 403
    data = request.get_json(force=True) or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'نام سمت الزامی است.'}), 400
    rid = DB.add_role(name)
    return jsonify({'ok': True, 'id': rid})


@app.route('/api/roles/<rid>', methods=['POST'])
def api_role_update(rid):
    user = require_auth()
    if not user or user['role'] != 'national':
        return jsonify({'error': 'دسترسی غیرمجاز.'}), 403
    data = request.get_json(force=True) or {}
    DB.update_role(rid, name=data.get('name'), active=data.get('active'))
    return jsonify({'ok': True})


@app.route('/api/roles/<rid>', methods=['DELETE'])
def api_role_delete(rid):
    user = require_auth()
    if not user or user['role'] != 'national':
        return jsonify({'error': 'دسترسی غیرمجاز.'}), 403
    DB.delete_role(rid)
    return jsonify({'ok': True})


# ----- API: Services -----
@app.route('/api/services', methods=['GET'])
def api_services():
    return jsonify({'services': DB.list_services()})


@app.route('/api/services', methods=['POST'])
def api_service_add():
    user = require_auth()
    if not user or user['role'] != 'national':
        return jsonify({'error': 'دسترسی غیرمجاز.'}), 403
    data = request.get_json(force=True) or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'نام خدمت الزامی است.'}), 400
    sid = DB.add_service(name)
    return jsonify({'ok': True, 'id': sid})


@app.route('/api/services/<sid>', methods=['POST'])
def api_service_update(sid):
    user = require_auth()
    if not user or user['role'] != 'national':
        return jsonify({'error': 'دسترسی غیرمجاز.'}), 403
    data = request.get_json(force=True) or {}
    DB.update_service(sid, name=data.get('name'), active=data.get('active'))
    return jsonify({'ok': True})


@app.route('/api/services/<sid>', methods=['DELETE'])
def api_service_delete(sid):
    user = require_auth()
    if not user or user['role'] != 'national':
        return jsonify({'error': 'دسترسی غیرمجاز.'}), 403
    DB.delete_service(sid)
    return jsonify({'ok': True})


# ----- API: Provinces & Counties -----
@app.route('/api/provinces', methods=['GET'])
def api_provinces():
    return jsonify({'provinces': DB.list_provinces()})


@app.route('/api/provinces', methods=['POST'])
def api_province_add():
    user = require_auth()
    if not user or user['role'] != 'national':
        return jsonify({'error': 'دسترسی غیرمجاز.'}), 403
    data = request.get_json(force=True) or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'نام استان الزامی است.'}), 400
    # Check for duplicate
    existing = DB._fetchone('SELECT id FROM provinces WHERE name=?', (name,))
    if existing:
        return jsonify({'error': 'استان با این نام قبلاً ثبت شده است.'}), 400
    try:
        pid = DB.add_province(name)
        return jsonify({'ok': True, 'id': pid})
    except Exception as e:
        return jsonify({'error': f'خطا در ثبت: {e}'}), 500


@app.route('/api/provinces/<pid>', methods=['DELETE'])
def api_province_delete(pid):
    user = require_auth()
    if not user or user['role'] != 'national':
        return jsonify({'error': 'دسترسی غیرمجاز.'}), 403
    DB.delete_province(pid)
    return jsonify({'ok': True})


@app.route('/api/counties', methods=['POST'])
def api_county_add():
    user = require_auth()
    if not user or user['role'] != 'national':
        return jsonify({'error': 'دسترسی غیرمجاز.'}), 403
    data = request.get_json(force=True) or {}
    province_id = data.get('province_id')
    name = (data.get('name') or '').strip()
    if not province_id or not name:
        return jsonify({'error': 'استان و نام شهرستان الزامی است.'}), 400
    # Check for duplicate within same province
    existing = DB._fetchone('SELECT id FROM counties WHERE province_id=? AND name=?', (province_id, name))
    if existing:
        return jsonify({'error': 'این شهرستان قبلاً برای این استان ثبت شده است.'}), 400
    try:
        cid = DB.add_county(province_id, name)
        return jsonify({'ok': True, 'id': cid})
    except Exception as e:
        return jsonify({'error': f'خطا در ثبت: {e}'}), 500


@app.route('/api/counties/<cid>', methods=['DELETE'])
def api_county_delete(cid):
    user = require_auth()
    if not user or user['role'] != 'national':
        return jsonify({'error': 'دسترسی غیرمجاز.'}), 403
    DB.delete_county(cid)
    return jsonify({'ok': True})


# ----- API: Sections (بخش‌ها) -----
@app.route('/api/sections', methods=['POST'])
def api_section_add():
    user = require_auth()
    if not user or user['role'] != 'national':
        return jsonify({'error': 'دسترسی غیرمجاز.'}), 403
    data = request.get_json(force=True) or {}
    county_id = data.get('county_id')
    name = (data.get('name') or '').strip()
    if not county_id or not name:
        return jsonify({'error': 'شهرستان و نام بخش الزامی است.'}), 400
    existing = DB._fetchone('SELECT id FROM sections WHERE county_id=? AND name=?', (county_id, name))
    if existing:
        return jsonify({'error': 'این بخش قبلاً برای این شهرستان ثبت شده است.'}), 400
    try:
        sid = DB.add_section(county_id, name)
        return jsonify({'ok': True, 'id': sid})
    except Exception as e:
        return jsonify({'error': f'خطا در ثبت: {e}'}), 500


@app.route('/api/sections/<sid>', methods=['DELETE'])
def api_section_delete(sid):
    user = require_auth()
    if not user or user['role'] != 'national':
        return jsonify({'error': 'دسترسی غیرمجاز.'}), 403
    DB.delete_section(sid)
    return jsonify({'ok': True})


# ----- API: Records -----
@app.route('/api/records', methods=['GET'])
def api_records_list():
    user = current_user()
    if not user:
        return jsonify({'error': 'ابتدا وارد شوید.'}), 401
    filters = {}
    if user['role'] == 'provincial':
        filters['province_id'] = user['province_id']
    elif user['role'] == 'county':
        filters['province_id'] = user['province_id']
        filters['county_id'] = user['county_id']
    # Optional filter params
    if request.args.get('province_id'):
        filters['province_id'] = request.args.get('province_id')
    if request.args.get('county_id'):
        filters['county_id'] = request.args.get('county_id')
    if request.args.get('village'):
        filters['village'] = request.args.get('village')
    return jsonify({'records': DB.list_records(filters)})


@app.route('/api/records', methods=['POST'])
def api_record_save():
    user = require_auth()
    if not user:
        return jsonify({'error': 'ابتدا وارد سامانه شوید.'}), 401
    data = request.get_json(force=True) or {}
    # Scope check
    if user['role'] == 'provincial':
        if data.get('provinceId') and data['provinceId'] != user['province_id']:
            return jsonify({'error': 'فقط در استان تخصیص‌یافته مجاز به ثبت هستید.'}), 403
    elif user['role'] == 'county':
        if data.get('provinceId') != user['province_id'] or data.get('countyId') != user['county_id']:
            return jsonify({'error': 'فقط در شهرستان تخصیص‌یافته مجاز به ثبت هستید.'}), 403
    if not data.get('village'):
        return jsonify({'error': 'نام روستا الزامی است.'}), 400
    if not data.get('serviceId'):
        return jsonify({'error': 'انتخاب خدمت الزامی است.'}), 400
    rid = DB.save_record(data, user_id=user['id'])
    return jsonify({'ok': True, 'id': rid})


@app.route('/api/records/<rid>', methods=['DELETE'])
def api_record_delete(rid):
    user = require_auth()
    if not user:
        return jsonify({'error': 'ابتدا وارد شوید.'}), 401
    rec = DB.get_record(rid)
    if not rec:
        return jsonify({'error': 'رکورد یافت نشد.'}), 404
    if user['role'] == 'provincial' and rec['province_id'] != user['province_id']:
        return jsonify({'error': 'دسترسی غیرمجاز.'}), 403
    elif user['role'] == 'county' and (rec['province_id'] != user['province_id'] or rec['county_id'] != user['county_id']):
        return jsonify({'error': 'دسترسی غیرمجاز.'}), 403
    DB.delete_record(rid)
    return jsonify({'ok': True})


# ----- API: Announcements -----
@app.route('/api/announcements', methods=['POST'])
def api_announcement_add():
    user = require_auth()
    if not user or user['role'] != 'national':
        return jsonify({'error': 'دسترسی غیرمجاز.'}), 403
    data = request.get_json(force=True) or {}
    text = (data.get('text') or '').strip()
    if not text:
        return jsonify({'error': 'متن اعلان الزامی است.'}), 400
    aid = DB.add_announcement(text)
    return jsonify({'ok': True, 'id': aid})


@app.route('/api/announcements/<aid>', methods=['DELETE'])
def api_announcement_delete(aid):
    user = require_auth()
    if not user or user['role'] != 'national':
        return jsonify({'error': 'دسترسی غیرمجاز.'}), 403
    DB.delete_announcement(aid)
    return jsonify({'ok': True})


# ----- API: Custom Fields -----
@app.route('/api/custom-fields', methods=['POST'])
def api_custom_field_add():
    user = require_auth()
    if not user or user['role'] != 'national':
        return jsonify({'error': 'دسترسی غیرمجاز.'}), 403
    data = request.get_json(force=True) or {}
    label = (data.get('label') or '').strip()
    if not label:
        return jsonify({'error': 'عنوان فیلد الزامی است.'}), 400
    fid = DB.add_custom_field(label, data.get('type', 'text'), data.get('scope', 'all'))
    return jsonify({'ok': True, 'id': fid})


@app.route('/api/custom-fields/<fid>', methods=['DELETE'])
def api_custom_field_delete(fid):
    user = require_auth()
    if not user or user['role'] != 'national':
        return jsonify({'error': 'دسترسی غیرمجاز.'}), 403
    DB.delete_custom_field(fid)
    return jsonify({'ok': True})


# ----- API: Settings -----
@app.route('/api/settings', methods=['POST'])
def api_settings_save():
    user = require_auth()
    if not user or user['role'] != 'national':
        return jsonify({'error': 'دسترسی غیرمجاز.'}), 403
    data = request.get_json(force=True) or {}
    # Convert booleans to '1'/'0'
    updates = {}
    for k, v in data.items():
        if isinstance(v, bool):
            updates[k] = '1' if v else '0'
        else:
            updates[k] = v
    DB.set_settings(updates)
    return jsonify({'ok': True})


# ----- API: Core fields -----
@app.route('/api/core-fields', methods=['POST'])
def api_core_fields_save():
    user = require_auth()
    if not user or user['role'] != 'national':
        return jsonify({'error': 'دسترسی غیرمجاز.'}), 403
    data = request.get_json(force=True) or {}
    fields = data.get('fields') or []
    for f in fields:
        DB.set_core_field(f['key'], f.get('label', ''), f.get('visible', True))
    return jsonify({'ok': True})


# ----- API: Users -----
@app.route('/api/users', methods=['POST'])
def api_user_save():
    user = require_auth()
    if not user or user['role'] not in ('national', 'provincial'):
        return jsonify({'error': 'دسترسی غیرمجاز.'}), 403
    data = request.get_json(force=True) or {}
    name = (data.get('name') or '').strip()
    # Phone number is used as username
    phone = (data.get('phone') or data.get('username') or '').strip()
    # Normalize phone: convert Persian digits, remove spaces
    phone = phone.replace(' ', '').replace('-', '')
    phone = phone.translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789'))
    password = data.get('password') or ''
    role = data.get('role', 'national')
    province_id = data.get('province_id') or ''
    county_id = data.get('county_id') or ''
    user_id = data.get('id')
    generated_password = None
    if not name or not phone:
        return jsonify({'error': 'نام و شماره تلفن همراه الزامی است.'}), 400
    # Provincial admin scoping: can only manage county users within own province
    if user['role'] == 'provincial':
        role = 'county'  # force county role
        province_id = user['province_id']  # lock to own province
        # If editing, ensure target is a county user in this province
        if user_id:
            target = DB.get_user(user_id)
            if not target:
                return jsonify({'error': 'کاربر یافت نشد.'}), 404
            if target['role'] != 'county' or target.get('province_id') != user['province_id']:
                return jsonify({'error': 'شما فقط می‌توانید کاربران شهرستانی استان خود را ویرایش کنید.'}), 403
        # Prevent editing the default admin
        if user_id == 'u_admin_default':
            return jsonify({'error': 'دسترسی غیرمجاز.'}), 403
    # Check username uniqueness
    existing = DB.get_user_by_username(phone)
    if existing and existing['id'] != user_id:
        return jsonify({'error': 'این شماره تلفن قبلاً ثبت شده است.'}), 409
    if user_id:
        # Update existing user — only change password if provided
        DB.update_user(user_id, name, phone, password if password else None, role, province_id, county_id, data.get('active', True))
    else:
        # New user — fixed default password 123456789
        generated_password = '123456789'
        user_id = DB.create_user(name, phone, generated_password, role, province_id, county_id)
    return jsonify({'ok': True, 'id': user_id, 'generated_password': generated_password, 'username': phone})


@app.route('/api/change-password', methods=['POST'])
def api_change_password():
    user = require_auth()
    if not user:
        return jsonify({'error': 'احراز هویت لازم است.'}), 401
    data = request.get_json(force=True) or {}
    new_pwd = data.get('new_password') or ''
    # Validate complexity
    import re
    if len(new_pwd) < 8:
        return jsonify({'error': 'رمز باید حداقل ۸ کاراکتر باشد.'}), 400
    if not re.search(r'\d', new_pwd):
        return jsonify({'error': 'رمز باید حداقل یک عدد داشته باشد.'}), 400
    if not re.search(r'[a-zA-Z]', new_pwd):
        return jsonify({'error': 'رمز باید حداقل یک حرف انگلیسی داشته باشد.'}), 400
    if not re.search(r'[!@#$%^&*()_+\-=\[\]{};:\'",.<>?/\\|`~]', new_pwd):
        return jsonify({'error': 'رمز باید حداقل یک نماد (!@#$...) داشته باشد.'}), 400
    # Update password
    full_user = DB.get_user_by_username(user['username'])
    if full_user:
        DB.update_user(full_user['id'], full_user['name'], full_user['username'], new_pwd, 
                       full_user['role'], full_user.get('province_id',''), full_user.get('county_id',''), 1)
    return jsonify({'ok': True})


@app.route('/api/users/<uid>/toggle', methods=['POST'])
def api_user_toggle(uid):
    user = require_auth()
    if not user or user['role'] not in ('national', 'provincial'):
        return jsonify({'error': 'دسترسی غیرمجاز.'}), 403
    data = request.get_json(force=True) or {}
    # Provincial scoping: only county users in own province
    if user['role'] == 'provincial':
        target = DB.get_user(uid)
        if not target or target['role'] != 'county' or target.get('province_id') != user['province_id']:
            return jsonify({'error': 'شما فقط به کاربران شهرستانی استان خود دسترسی دارید.'}), 403
    DB.toggle_user(uid, data.get('active', True))
    return jsonify({'ok': True})


@app.route('/api/users/<uid>', methods=['DELETE'])
def api_user_delete(uid):
    user = require_auth()
    if not user or user['role'] not in ('national', 'provincial'):
        return jsonify({'error': 'دسترسی غیرمجاز.'}), 403
    if uid == 'u_admin_default':
        return jsonify({'error': 'حذف حساب مدیر اصلی ممکن نیست.'}), 400
    if uid == user['id']:
        return jsonify({'error': 'نمی‌توانید حساب خودتان را حذف کنید.'}), 400
    # Provincial scoping: only county users in own province
    if user['role'] == 'provincial':
        target = DB.get_user(uid)
        if not target or target['role'] != 'county' or target.get('province_id') != user['province_id']:
            return jsonify({'error': 'شما فقط می‌توانید کاربران شهرستانی استان خود را حذف کنید.'}), 403
    ok = DB.delete_user(uid)
    if not ok:
        return jsonify({'error': 'حذف این کاربر ممکن نیست.'}), 400
    return jsonify({'ok': True})


@app.route('/api/users/<uid>/reset-password', methods=['POST'])
def api_user_reset_password(uid):
    """Reset a user's password to the fixed default 123456789 (national/provincial admin)."""
    user = require_auth()
    if not user or user['role'] not in ('national', 'provincial'):
        return jsonify({'error': 'دسترسی غیرمجاز.'}), 403
    target = DB.get_user(uid)
    if not target:
        return jsonify({'error': 'کاربر یافت نشد.'}), 404
    # Provincial scoping: only county users in own province
    if user['role'] == 'provincial':
        if target['role'] != 'county' or target.get('province_id') != user['province_id']:
            return jsonify({'error': 'شما فقط می‌توانید رمز کاربران شهرستانی استان خود را ریست کنید.'}), 403
    default_pwd = '123456789'
    DB.update_user(uid, target['name'], target['username'], default_pwd,
                   target['role'], target.get('province_id') or '', target.get('county_id') or '',
                   target.get('active', 1))
    return jsonify({'ok': True, 'new_password': default_pwd})


# ----- API: Geo catalog -----
@app.route('/api/geo/import', methods=['POST'])
def api_geo_import():
    user = require_auth()
    if not user or user['role'] != 'national':
        return jsonify({'error': 'دسترسی غیرمجاز.'}), 403
    data = request.get_json(force=True) or {}
    entries = data.get('entries') or []
    if not entries:
        return jsonify({'error': 'داده‌ای برای بارگذاری وجود ندارد.'}), 400
    DB.clear_geo_catalog()
    DB.add_geo_entries(entries)
    return jsonify({'ok': True, 'count': len(entries)})


# ----- API: Backup / Export -----
@app.route('/api/export/csv', methods=['GET'])
def api_export_csv():
    user = current_user()
    if not user:
        return jsonify({'error': 'ابتدا وارد شوید.'}), 401
    filters = {}
    if user['role'] == 'provincial':
        filters['province_id'] = user['province_id']
    elif user['role'] == 'county':
        filters['province_id'] = user['province_id']
        filters['county_id'] = user['county_id']
    records = DB.list_records(filters)
    output = io.StringIO()
    output.write('\ufeff')  # BOM for Excel
    writer = csv.writer(output)
    writer.writerow(['کارشناس', 'سمت', 'واحد', 'استان', 'شهرستان', 'دهستان', 'روستا', 'خدمت', 'تاریخ', 'بهرهمندان', 'شرح', 'مستندات'])
    for r in records:
        writer.writerow([
            r.get('expert_name', ''), r.get('role_name', ''), r.get('org', ''),
            r.get('province_name', ''), r.get('county_name', ''),
            r.get('district_name', ''), r.get('village', ''),
            r.get('service_name', ''), r.get('service_date', ''),
            r.get('beneficiaries', 0), r.get('description', ''), r.get('evidence', '')
        ])
    resp = make_response(output.getvalue())
    resp.headers['Content-Type'] = 'text/csv; charset=utf-8'
    resp.headers['Content-Disposition'] = 'attachment; filename="rural_services.csv"'
    return resp


@app.route('/api/export/json', methods=['GET'])
def api_export_json():
    user = current_user()
    if not user:
        return jsonify({'error': 'ابتدا وارد شوید.'}), 401
    if user['role'] != 'national':
        # Non-admins get a scoped export
        filters = {}
        if user['role'] == 'provincial':
            filters['province_id'] = user['province_id']
        elif user['role'] == 'county':
            filters['province_id'] = user['province_id']
            filters['county_id'] = user['county_id']
        records = DB.list_records(filters)
        return jsonify({'records': records, 'exported_at': DB.now_iso()})
    data = DB.export_all_data()
    resp = make_response(json.dumps(data, ensure_ascii=False, indent=2))
    resp.headers['Content-Type'] = 'application/json; charset=utf-8'
    resp.headers['Content-Disposition'] = 'attachment; filename="rural_backup.json"'
    return resp


# ===== API: PLAN MANAGEMENT (سامانه طرح‌های پویا) =====

STATUS_LABELS = {'done': 'انجام‌شده', 'in_progress': 'در حال انجام', 'capacity': 'دارای ظرفیت انجام'}

@app.route('/api/plans', methods=['GET'])
def api_plans_list():
    user = current_user()
    if not user:
        return jsonify({'error': 'احراز هویت لازم است.'}), 401
    search = request.args.get('search', '')
    active_only = request.args.get('active_only', '0') == '1'
    plans = DB.list_plans(active_only=active_only, search=search)
    return jsonify(plans)


@app.route('/api/plans', methods=['POST'])
def api_plan_add():
    user = require_auth()
    if not user or user['role'] != 'national':
        return jsonify({'error': 'دسترسی غیرمجاز. مدیریت طرح‌ها فقط برای نقش کشوری.'}), 403
    data = request.get_json(force=True) or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'عنوان طرح الزامی است.'}), 400
    description = (data.get('description') or '').strip()
    allowed = data.get('allowed_statuses') or ['done', 'in_progress', 'capacity']
    allow_dup = 1 if data.get('allow_duplicate') else 0
    sort_order = int(data.get('sort_order', 0) or 0)
    pid = DB.add_plan(name, description, allowed, allow_dup, sort_order, user['id'])
    return jsonify({'ok': True, 'id': pid})


@app.route('/api/plans/<pid>', methods=['POST'])
def api_plan_update(pid):
    user = require_auth()
    if not user or user['role'] != 'national':
        return jsonify({'error': 'دسترسی غیرمجاز.'}), 403
    data = request.get_json(force=True) or {}
    DB.update_plan(pid,
        name=data.get('name'),
        description=data.get('description'),
        active=data.get('active'),
        allow_duplicate=data.get('allow_duplicate'),
        sort_order=data.get('sort_order'),
        allowed_statuses=data.get('allowed_statuses'))
    return jsonify({'ok': True})


@app.route('/api/plans/<pid>', methods=['DELETE'])
def api_plan_delete(pid):
    user = require_auth()
    if not user or user['role'] != 'national':
        return jsonify({'error': 'دسترسی غیرمجاز.'}), 403
    hard = request.args.get('hard') == '1'
    if hard:
        DB.hard_delete_plan(pid)
    else:
        DB.delete_plan(pid)
    return jsonify({'ok': True})


@app.route('/api/plans/<pid>/fields', methods=['GET'])
def api_plan_fields_list(pid):
    user = current_user()
    if not user:
        return jsonify({'error': 'احراز هویت لازم است.'}), 401
    fields = DB.list_plan_fields(pid, active_only=(request.args.get('all') != '1'))
    return jsonify(fields)


@app.route('/api/plans/<pid>/fields', methods=['POST'])
def api_plan_field_add(pid):
    user = require_auth()
    if not user or user['role'] != 'national':
        return jsonify({'error': 'دسترسی غیرمجاز.'}), 403
    data = request.get_json(force=True) or {}
    field_key = (data.get('field_key') or '').strip()
    label = (data.get('label') or '').strip()
    if not label:
        return jsonify({'error': 'عنوان فیلد الزامی است.'}), 400
    if not field_key:
        import re
        field_key = re.sub(r'\s+', '_', label)[:30]
    fid = DB.add_plan_field(pid, field_key, label,
        data.get('type', 'text'),
        1 if data.get('required') else 0,
        data.get('options'),
        data.get('help_text', ''),
        int(data.get('sort_order', 0) or 0))
    return jsonify({'ok': True, 'id': fid})


@app.route('/api/plan-fields/<fid>', methods=['POST'])
def api_plan_field_update(fid):
    user = require_auth()
    if not user or user['role'] != 'national':
        return jsonify({'error': 'دسترسی غیرمجاز.'}), 403
    data = request.get_json(force=True) or {}
    DB.update_plan_field(fid,
        field_key=data.get('field_key'),
        label=data.get('label'),
        field_type=data.get('type'),
        required=data.get('required'),
        options=data.get('options'),
        help_text=data.get('help_text'),
        sort_order=data.get('sort_order'),
        active=data.get('active'))
    return jsonify({'ok': True})


@app.route('/api/plan-fields/<fid>', methods=['DELETE'])
def api_plan_field_delete(fid):
    user = require_auth()
    if not user or user['role'] != 'national':
        return jsonify({'error': 'دسترسی غیرمجاز.'}), 403
    DB.delete_plan_field(fid)
    return jsonify({'ok': True})


@app.route('/api/plan-records', methods=['GET'])
def api_plan_records_list():
    user = current_user()
    if not user:
        return jsonify({'error': 'احراز هویت لازم است.'}), 401
    filters = {}
    for k in ('plan_id', 'village', 'province_id', 'county_id', 'status_category'):
        v = request.args.get(k)
        if v:
            filters[k] = v
    # Scope by user role
    if user['role'] == 'provincial':
        filters['province_id'] = user.get('province_id') or ''
    elif user['role'] == 'county':
        filters['county_id'] = user.get('county_id') or ''
    records = DB.list_plan_records(filters if filters else None)
    return jsonify(records)


@app.route('/api/plan-records', methods=['POST'])
def api_plan_record_add():
    user = require_auth()
    if not user:
        return jsonify({'error': 'احراز هویت لازم است.'}), 401
    data = request.get_json(force=True) or {}
    plan_id = data.get('plan_id')
    village = (data.get('village') or '').strip()
    status_category = data.get('status_category')
    if not plan_id or not village or not status_category:
        return jsonify({'error': 'طرح، روستا و وضعیت الزامی است.'}), 400
    # Server-side required field validation (only for 'done' status)
    fields = DB.list_plan_fields(plan_id)
    values = data.get('field_values') or {}
    errors = []
    if status_category == 'done':
        for f in fields:
            if f['required'] and not values.get(f['field_key']):
                errors.append(f"فیلد «{f['label']}» اجباری است.")
    if errors:
        return jsonify({'error': ' | '.join(errors)}), 400
    # Scope check
    province_id = data.get('province_id', '')
    county_id = data.get('county_id', '')
    if user['role'] == 'provincial' and user.get('province_id') and province_id != user['province_id']:
        return jsonify({'error': 'ثبت خارج از محدوده استان مجاز نیست.'}), 403
    if user['role'] == 'county' and user.get('county_id') and county_id != user['county_id']:
        return jsonify({'error': 'ثبت خارج از محدوده شهرستان مجاز نیست.'}), 403
    try:
        rid = DB.add_plan_record(plan_id, village, status_category, values,
            province_id=province_id, county_id=county_id,
            section_id=data.get('section_id', ''),
            district_id=data.get('district_id', ''),
            expert_name=data.get('expert_name', ''),
            role_id=data.get('role_id', ''),
            org=data.get('org', ''),
            service_date=data.get('service_date', ''),
            description=data.get('description', ''),
            created_by=user['id'])
        return jsonify({'ok': True, 'id': rid})
    except ValueError as e:
        return jsonify({'error': str(e), 'duplicate': True}), 409


@app.route('/api/plan-records/<rid>', methods=['POST'])
def api_plan_record_update(rid):
    user = require_auth()
    if not user:
        return jsonify({'error': 'احراز هویت لازم است.'}), 401
    data = request.get_json(force=True) or {}
    record = DB.get_plan_record(rid)
    if not record:
        return jsonify({'error': 'رکورد یافت نشد.'}), 404
    # Scope check
    if user['role'] == 'provincial' and record.get('province_id') != user.get('province_id'):
        return jsonify({'error': 'دسترسی غیرمجاز.'}), 403
    if user['role'] == 'county' and record.get('county_id') != user.get('county_id'):
        return jsonify({'error': 'دسترسی غیرمجاز.'}), 403
    if 'status_category' in data and data['status_category'] != record.get('status_category'):
        DB.update_plan_record_status(rid, data['status_category'], user['id'], data.get('note', ''))
    DB.update_plan_record(rid,
        field_values=data.get('field_values'),
        expert_name=data.get('expert_name'),
        org=data.get('org'),
        service_date=data.get('service_date'),
        description=data.get('description'))
    return jsonify({'ok': True})


@app.route('/api/plan-records/<rid>', methods=['DELETE'])
def api_plan_record_delete(rid):
    user = require_auth()
    if not user:
        return jsonify({'error': 'احراز هویت لازم است.'}), 401
    record = DB.get_plan_record(rid)
    if not record:
        return jsonify({'error': 'رکورد یافت نشد.'}), 404
    if user['role'] == 'provincial' and record.get('province_id') != user.get('province_id'):
        return jsonify({'error': 'دسترسی غیرمجاز.'}), 403
    if user['role'] == 'county' and record.get('county_id') != user.get('county_id'):
        return jsonify({'error': 'دسترسی غیرمجاز.'}), 403
    DB.delete_plan_record(rid)
    return jsonify({'ok': True})


@app.route('/api/plan-records/<rid>/history', methods=['GET'])
def api_plan_record_history(rid):
    user = current_user()
    if not user:
        return jsonify({'error': 'احراز هویت لازم است.'}), 401
    return jsonify(DB.get_status_history(rid))


@app.route('/api/plan-stats', methods=['GET'])
def api_plan_stats():
    user = current_user()
    if not user:
        return jsonify({'error': 'احراز هویت لازم است.'}), 401
    return jsonify(DB.get_plan_stats())


@app.route('/api/plan-report', methods=['GET'])
def api_plan_report():
    """Generate a report with filters. Supports CSV export."""
    user = current_user()
    if not user:
        return jsonify({'error': 'احراز هویت لازم است.'}), 401
    filters = {}
    for k in ('plan_id', 'village', 'province_id', 'county_id', 'status_category'):
        v = request.args.get(k)
        if v:
            filters[k] = v
    if user['role'] == 'provincial':
        filters['province_id'] = user.get('province_id') or ''
    elif user['role'] == 'county':
        filters['county_id'] = user.get('county_id') or ''
    records = DB.list_plan_records(filters if filters else None)
    # Enrich with plan name, province name, county name, status label
    plan_cache = {}
    prov_cache = {}
    county_cache = {}
    provinces_list = DB.list_provinces()
    for r in records:
        pid = r.get('plan_id')
        if pid not in plan_cache:
            plan_cache[pid] = DB.get_plan(pid)
        p = plan_cache.get(pid) or {}
        r['plan_name'] = p.get('name', '')
        # Province name
        prov_id = r.get('province_id')
        if prov_id:
            if prov_id not in prov_cache:
                prov = next((p2 for p2 in provinces_list if p2['id'] == prov_id), None)
                prov_cache[prov_id] = prov.get('name', '') if prov else ''
            r['province_name'] = prov_cache.get(prov_id, '')
        else:
            r['province_name'] = ''
        # County name
        cty_id = r.get('county_id')
        if cty_id:
            if cty_id not in county_cache:
                for p2 in provinces_list:
                    for c in (p2.get('counties') or []):
                        if c['id'] == cty_id:
                            county_cache[cty_id] = c.get('name', '')
                            break
            r['county_name'] = county_cache.get(cty_id, '')
        else:
            r['county_name'] = ''
        r['status_label'] = STATUS_LABELS.get(r.get('status_category'), r.get('status_category', ''))
    # CSV export
    if request.args.get('format') == 'csv':
        import csv, io
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(['طرح', 'روستا', 'وضعیت', 'کارشناس', 'واحد', 'تاریخ', 'توضیحات', 'تاریخ ثبت'])
        for r in records:
            w.writerow([r.get('plan_name',''), r.get('village',''), r.get('status_label',''),
                       r.get('expert_name',''), r.get('org',''), r.get('service_date',''),
                       r.get('description',''), r.get('created_at','')])
        resp = make_response(out.getvalue())
        resp.headers['Content-Type'] = 'text/csv; charset=utf-8'
        resp.headers['Content-Disposition'] = 'attachment; filename="plan_report.csv"'
        return resp
    return jsonify(records)


# ----- Main -----
# Initialize database on module load (so Gunicorn import also inits DB)
# This is needed for platforms like Render where the app is started via gunicorn
# rather than `python app.py`. Safe to call multiple times (uses CREATE TABLE IF NOT EXISTS).
DB.init_db()


def main():
    port = int(os.environ.get('PORT', 5050))
    debug = os.environ.get('FLASK_DEBUG', '0') == '1'
    print(f'[app] Rural Services System starting on http://localhost:{port}')
    app.run(host='0.0.0.0', port=port, debug=debug, threaded=True)


if __name__ == '__main__':
    main()


# ===== API: FORGOT PASSWORD (فراموشی رمز) =====
@app.route('/api/forgot-password', methods=['POST'])
def api_forgot_password():
    """Public endpoint — create or check password reset request."""
    data = request.get_json(force=True) or {}
    name = (data.get('name') or '').strip()
    username = (data.get('username') or '').strip()
    province_id = data.get('province_id') or ''
    county_id = data.get('county_id') or ''
    if not name or not username:
        return jsonify({'error': 'نام و شماره تلفن الزامی است.'}), 400
    # Normalize phone
    username = username.replace(' ', '').replace('-', '')
    username = username.translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789'))
    # Check if user exists
    user = DB.get_user_by_username(username)
    if not user:
        return jsonify({'error': 'اطلاعات شما در سامانه ثبت نشده است.'}), 404
    if not user.get('active'):
        return jsonify({'error': 'این حساب غیرفعال است.'}), 403
    # Verify name matches
    if user['name'].strip() != name:
        return jsonify({'error': 'نام واردشده با نام ثبت‌شده در سامانه مطابقت ندارد.'}), 400
    # Verify province matches (if user has a province)
    if user.get('province_id'):
        if province_id and province_id != user['province_id']:
            return jsonify({'error': 'استان واردشده با استان ثبت‌شده در سامانه مطابقت ندارد.'}), 400
    # Verify county matches (if user has a county)
    if user.get('county_id'):
        if county_id and county_id != user['county_id']:
            return jsonify({'error': 'شهرستان واردشده با شهرستان ثبت‌شده در سامانه مطابقت ندارد.'}), 400
    # Check for existing requests (any status)
    existing = DB._fetchone(
        'SELECT * FROM password_reset_requests WHERE username=? ORDER BY created_at DESC LIMIT 1',
        (username,))
    if existing:
        status = existing['status']
        if status == 'pending':
            return jsonify({'status': 'pending', 'message': 'درخواست شما در حال رسیدگی می‌باشد.'})
        elif status == 'approved':
            return jsonify({'status': 'approved', 'message': 'رمز شما به ۱۲۳۴۵۶۷۸۹ تغییر یافت. لطفاً با این رمز وارد شوید.'})
        # If rejected, allow creating a new request (fall through)
    # Create new request
    rid = DB.create_reset_request(user['id'], name, username, province_id, county_id, user['role'])
    return jsonify({'ok': True, 'status': 'created', 'message': 'درخواست شما با موفقیت ثبت شد. ظرف سه روز آینده با ورود مجدد اطلاعات، نتیجه را در همین صفحه مشاهده نمائید.'})


@app.route('/api/reset-requests', methods=['GET'])
def api_reset_requests_list():
    """List pending reset requests for admin."""
    user = current_user()
    if not user or user['role'] == 'county':
        return jsonify({'error': 'دسترسی غیرمجاز.'}), 403
    status = request.args.get('status', 'pending')
    prov_id = user.get('province_id') if user['role'] == 'provincial' else None
    reqs = DB.list_reset_requests(status=status, admin_role=user['role'], admin_province_id=prov_id)
    # Enrich with province/county names
    provinces_list = DB.list_provinces()
    for r in reqs:
        pid = r.get('province_id')
        if pid:
            prov = next((p for p in provinces_list if p['id'] == pid), None)
            r['province_name'] = prov.get('name', '') if prov else ''
        else:
            r['province_name'] = ''
        cid = r.get('county_id')
        if cid:
            for p in provinces_list:
                for c in (p.get('counties') or []):
                    if c['id'] == cid:
                        r['county_name'] = c.get('name', '')
                        break
        else:
            r['county_name'] = ''
    return jsonify(reqs)


@app.route('/api/reset-requests/<rid>/approve', methods=['POST'])
def api_reset_approve(rid):
    user = require_auth()
    if not user or user['role'] == 'county':
        return jsonify({'error': 'دسترسی غیرمجاز. فقط مدیر استانی یا کشوری.'}), 403
    try:
        DB.approve_reset_request(rid, user['id'])
        return jsonify({'ok': True, 'message': 'درخواست تأیید شد. رمز به 123456789 بازگردانده شد.'})
    except ValueError as e:
        return jsonify({'error': str(e)}), 404


@app.route('/api/reset-requests/<rid>/reject', methods=['POST'])
def api_reset_reject(rid):
    user = require_auth()
    if not user or user['role'] == 'county':
        return jsonify({'error': 'دسترسی غیرمجاز.'}), 403
    DB.reject_reset_request(rid, user['id'])
    return jsonify({'ok': True, 'message': 'درخواست رد شد.'})

# ===== API: MESSAGING (پیام‌رسانی) =====
@app.route('/api/messages', methods=['GET'])
def api_messages_list():
    user = current_user()
    if not user:
        return jsonify({'error': 'احراز هویت لازم است.'}), 401
    sent = request.args.get('sent') == '1'
    if sent:
        return jsonify(DB.list_sent(user['id']))
    return jsonify(DB.list_inbox(user['id'], user['role'],
                                user.get('province_id'), user.get('county_id')))


@app.route('/api/messages', methods=['POST'])
def api_message_send():
    user = require_auth()
    if not user:
        return jsonify({'error': 'احراز هویت لازم است.'}), 401
    data = request.get_json(force=True) or {}
    target_role = data.get('target_role')
    subject = (data.get('subject') or '').strip()
    body = (data.get('body') or '').strip()
    if not target_role or not subject or not body:
        return jsonify({'error': 'گیرنده، موضوع و متن پیام الزامی است.'}), 400
    # Determine target scope based on sender's role
    target_province_id = None
    target_county_id = None
    if user['role'] == 'county':
        # County can send to provincial (their province) or national
        if target_role == 'provincial':
            target_province_id = user.get('province_id')
    elif user['role'] == 'provincial':
        # Provincial can send to national or county (their province)
        if target_role == 'county':
            target_province_id = user.get('province_id')
    elif user['role'] == 'national':
        # National can send to provincial or county (optionally scoped)
        target_province_id = data.get('target_province_id') or None
        target_county_id = data.get('target_county_id') or None
    mid = DB.send_message(user['id'], user.get('name',''), user['role'],
                          target_role, subject, body, target_province_id, target_county_id)
    return jsonify({'ok': True, 'id': mid})


@app.route('/api/messages/<mid>/read', methods=['POST'])
def api_message_read(mid):
    user = require_auth()
    if not user:
        return jsonify({'error': 'احراز هویت لازم است.'}), 401
    DB.mark_message_read(mid)
    return jsonify({'ok': True})


@app.route('/api/messages/<mid>', methods=['DELETE'])
def api_message_delete(mid):
    user = require_auth()
    if not user:
        return jsonify({'error': 'احراز هویت لازم است.'}), 401
    DB.delete_message(mid)
    return jsonify({'ok': True})


@app.route('/api/messages/unread-count', methods=['GET'])
def api_unread_count():
    user = current_user()
    if not user:
        return jsonify({'count': 0})
    count = DB.get_unread_count(user['id'], user['role'],
                                user.get('province_id'), user.get('county_id'))
    return jsonify({'count': count})
