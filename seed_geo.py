"""Seed Iran's administrative divisions into the database.

Reads CSV files from the data/ folder and bulk-inserts:
- provinces (استان) — 31 records
- counties (شهرستان) — 484 records
- sections/districts (بخش) — 1,193 records
- dehestan/rurals (دهستان) — 2,777 records

Data source: sajaddp/list-of-cities-in-Iran (GitHub, CC-BY, up to 1404)

Usage: called via /api/seed-geo endpoint (national admin only).
Idempotent: skips entries that already exist.
"""
import os
import csv

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')


def _read_csv(filename):
    """Read a CSV file from the data directory."""
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return list(reader)


def seed_all_geo(DB):
    """Bulk-insert all administrative divisions. Returns a summary dict."""
    summary = {'provinces': 0, 'counties': 0, 'sections': 0, 'dehestan': 0, 'skipped': 0}

    # 1. Provinces (استان)
    for row in _read_csv('provinces.csv'):
        pid = row['id'].strip()
        name = row['name'].strip()
        if not pid or not name:
            continue
        existing = DB._fetchone('SELECT id FROM provinces WHERE id=?', (pid,))
        if existing:
            summary['skipped'] += 1
            continue
        DB._exec('INSERT INTO provinces(id, name) VALUES (?,?)', (pid, name))
        summary['provinces'] += 1

    # 2. Counties (شهرستان)
    for row in _read_csv('counties.csv'):
        cid = row['id'].strip()
        name = row['name'].strip()
        pid = row['province_id'].strip()
        if not cid or not name or not pid:
            continue
        existing = DB._fetchone('SELECT id FROM counties WHERE id=?', (cid,))
        if existing:
            summary['skipped'] += 1
            continue
        DB._exec('INSERT INTO counties(id, province_id, name) VALUES (?,?,?)', (cid, pid, name))
        summary['counties'] += 1

    # 3. Sections / Districts (بخش)
    for row in _read_csv('districts.csv'):
        sid = row['id'].strip()
        name = row['name'].strip()
        cid = row['county_id'].strip()
        if not sid or not name or not cid:
            continue
        existing = DB._fetchone('SELECT id FROM sections WHERE id=?', (sid,))
        if existing:
            summary['skipped'] += 1
            continue
        DB._exec('INSERT INTO sections(id, county_id, name) VALUES (?,?,?)', (sid, cid, name))
        summary['sections'] += 1

    # 4. Dehestan / Rural Districts (دهستان)
    for row in _read_csv('rurals.csv'):
        did = row['id'].strip()
        name = row['name'].strip()
        cid = row['county_id'].strip()
        sid = row.get('district_id', '').strip()
        if not did or not name or not cid:
            continue
        existing = DB._fetchone('SELECT id FROM districts WHERE id=?', (did,))
        if existing:
            summary['skipped'] += 1
            continue
        DB._exec(
            'INSERT INTO districts(id, county_id, section_id, name) VALUES (?,?,?,?)',
            (did, cid, sid or None, name)
        )
        summary['dehestan'] += 1

    return summary
