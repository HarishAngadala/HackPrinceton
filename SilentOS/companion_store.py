"""Durable, approval-gated Photon conversations for the optional companion."""
import json
import os
from contextlib import contextmanager
from pathlib import Path
import secrets
import sqlite3
import time

from commands import clean, default_path


class CompanionStore:
    def __init__(self, path=None):
        self.path = Path(path or default_path().parent / 'companion.sqlite3')
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY, space_id TEXT NOT NULL, sender_id TEXT NOT NULL,
                agent_id TEXT NOT NULL, sender_handle TEXT NOT NULL, platform TEXT NOT NULL,
                text TEXT NOT NULL, status TEXT NOT NULL, reply TEXT NOT NULL DEFAULT '',
                detail TEXT NOT NULL DEFAULT '', external_id TEXT,
                created_at TEXT NOT NULL, updated REAL NOT NULL, claim_token TEXT)''')
            db.execute('''CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY, value TEXT NOT NULL)''')
        os.chmod(self.path, 0o600)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def public(row):
        return {key: row[key] for key in ('id','space_id','sender_handle','platform','text','status',
                                           'reply','detail','external_id','created_at','updated')}

    def ingest(self, item):
        required = {
            'id': 100, 'space_id': 100, 'sender_id': 100, 'agent_id': 100,
            'sender_handle': 320, 'platform': 32, 'text': 8000, 'created_at': 80,
        }
        data = {name: clean(item.get(name), name.replace('_',' ').title(), limit)
                for name,limit in required.items()}
        if data['platform'] != 'imessage':
            raise ValueError('The companion currently accepts iMessage only')
        now = time.time()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM messages WHERE id=?',(data['id'],)).fetchone()
            if row:
                existing = {key:row[key] for key in required}
                if existing != data:
                    raise ValueError('Photon message ID belongs to different content')
                return self.public(row)
            db.execute('''INSERT INTO messages
                (id,space_id,sender_id,agent_id,sender_handle,platform,text,status,created_at,updated)
                VALUES (?,?,?,?,?,?,?,'received',?,?)''',
                tuple(data[key] for key in ('id','space_id','sender_id','agent_id','sender_handle','platform','text','created_at'))+(now,))
            return self.public(db.execute('SELECT * FROM messages WHERE id=?',(data['id'],)).fetchone())

    def list(self, limit=50):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('Limit must be between 1 and 100')
        with self.connect() as db:
            return [self.public(row) for row in db.execute(
                'SELECT * FROM messages ORDER BY updated DESC LIMIT ?', (limit,))]

    def history(self, space_id, limit=12):
        space_id = clean(space_id, 'Space ID', 100)
        with self.connect() as db:
            rows = db.execute('SELECT * FROM messages WHERE space_id=? ORDER BY created_at DESC LIMIT ?',
                              (space_id,limit)).fetchall()
            return [self.public(row) for row in reversed(rows)]

    def _claim(self, source, target):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM messages WHERE status=? ORDER BY created_at,id LIMIT 1',(source,)).fetchone()
            if not row:return None
            token=secrets.token_urlsafe(24)
            db.execute('UPDATE messages SET status=?,claim_token=?,updated=? WHERE id=?',
                       (target,token,time.time(),row['id']))
            result=self.public(db.execute('SELECT * FROM messages WHERE id=?',(row['id'],)).fetchone())
            result['claim_token']=token
            result['sender_id']=row['sender_id'];result['agent_id']=row['agent_id']
            return result

    def claim_for_draft(self):
        return self._claim('received','processing')

    def claim_for_send(self):
        return self._claim('approved','sending')

    def _finish(self, message_id, token, expected, status, **fields):
        message_id=clean(message_id,'Message ID',100)
        if not isinstance(token,str) or not token:raise ValueError('Claim token required')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM messages WHERE id=?',(message_id,)).fetchone()
            if not row or row['status']!=expected or not row['claim_token'] or not secrets.compare_digest(row['claim_token'].encode(),token.encode()):
                raise ValueError('Invalid message state or claim token')
            allowed={'reply','detail','external_id'}
            if set(fields)-allowed:raise ValueError('Unknown result field')
            assignments=['status=?','claim_token=NULL','updated=?'];values=[status,time.time()]
            for name,value in fields.items():
                limit=8000 if name=='reply' else 1000 if name=='detail' else 100
                assignments.append(name+'=?');values.append(clean(value,name.replace('_',' ').title(),limit))
            values.append(message_id)
            db.execute(f"UPDATE messages SET {','.join(assignments)} WHERE id=?",values)
            return self.public(db.execute('SELECT * FROM messages WHERE id=?',(message_id,)).fetchone())

    def save_draft(self, message_id, token, reply):
        return self._finish(message_id,token,'processing','draft',reply=reply,
                            detail='Deep Agent prepared a reply. Review it before approval.')

    def block_draft(self, message_id, token, detail):
        return self._finish(message_id,token,'processing','blocked',detail=detail)

    def approve(self, message_id, reply=None):
        message_id=clean(message_id,'Message ID',100)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM messages WHERE id=?',(message_id,)).fetchone()
            if not row or row['status']!='draft':raise ValueError('Only a draft can be approved')
            chosen=clean(reply if reply is not None else row['reply'],'Reply',8000)
            db.execute("UPDATE messages SET reply=?,status='approved',detail='Approved locally; waiting for Photon.',updated=? WHERE id=?",
                       (chosen,time.time(),message_id))
            return self.public(db.execute('SELECT * FROM messages WHERE id=?',(message_id,)).fetchone())

    def dismiss(self, message_id):
        message_id=clean(message_id,'Message ID',100)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM messages WHERE id=?',(message_id,)).fetchone()
            if not row or row['status'] not in ('received','draft','blocked','uncertain'):
                raise ValueError('This message cannot be dismissed while work may be running')
            db.execute("UPDATE messages SET status='dismissed',detail='Dismissed locally; no reply sent.',updated=? WHERE id=?",
                       (time.time(),message_id))
            return self.public(db.execute('SELECT * FROM messages WHERE id=?',(message_id,)).fetchone())

    def retry_blocked(self, message_id):
        message_id=clean(message_id,'Message ID',100)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM messages WHERE id=?',(message_id,)).fetchone()
            if not row or row['status']!='blocked':
                raise ValueError('Only a definitively blocked message can be retried')
            target='draft' if row['reply'] else 'received'
            detail=('Returned to draft for fresh approval.' if target=='draft' else
                    'Queued for a new Deep Agent draft attempt.')
            db.execute('UPDATE messages SET status=?,detail=?,claim_token=NULL,updated=? WHERE id=?',
                       (target,detail,time.time(),message_id))
            return self.public(db.execute('SELECT * FROM messages WHERE id=?',(message_id,)).fetchone())

    def mark_sent(self, message_id, token, external_id):
        return self._finish(message_id,token,'sending','accepted',external_id=external_id,
                            detail='Photon accepted the approved reply. This is not a delivery receipt.')

    def mark_uncertain(self, message_id, token, detail):
        return self._finish(message_id,token,'sending','uncertain',detail=detail)

    def block_send(self, message_id, token, detail):
        return self._finish(message_id,token,'sending','blocked',detail=detail)

    def metadata(self, key, default=None):
        with self.connect() as db:
            row=db.execute('SELECT value FROM metadata WHERE key=?',(key,)).fetchone()
            return row['value'] if row else default

    def set_metadata(self, key, value):
        key=clean(key,'Metadata key',100);value=clean(value,'Metadata value',1000)
        with self.connect() as db:
            db.execute('INSERT INTO metadata(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,value))

    def heartbeat(self, photon_enabled):
        self.set_metadata('worker_last_seen',str(time.time()))
        self.set_metadata('worker_photon_enabled','true' if photon_enabled else 'false')

    def runtime_status(self, stale_after=70):
        value=self.metadata('worker_last_seen')
        try:last_seen=float(value)
        except (TypeError,ValueError):last_seen=None
        active=last_seen is not None and 0 <= time.time()-last_seen <= stale_after
        return {'worker_active':active,'worker_last_seen':last_seen,
                'worker_photon_enabled':self.metadata('worker_photon_enabled')=='true'}
