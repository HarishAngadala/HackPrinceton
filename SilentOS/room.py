"""Ephemeral two-device caption rooms for a trusted LAN demo."""
import secrets
import threading
import time

LOCK = threading.Lock()
ROOMS = {}
TTL = 3600


def create():
    now = time.time()
    with LOCK:
        for key in list(ROOMS):
            if ROOMS[key]['expires'] < now:
                del ROOMS[key]
        if len(ROOMS) >= 20:
            raise ValueError('Room limit reached; restart the server to clear old rooms.')
        room = secrets.token_urlsafe(18)
        speaker, listener = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
        ROOMS[room] = {'speaker': speaker, 'listener': listener, 'expires': now + TTL,
                       'messages': [], 'requests': {}, 'listener_seen': 0, 'ack': 0}
    return {'room': room, 'speaker_token': speaker, 'listener_token': listener}


def access(room_id, token, role):
    room = ROOMS.get(room_id)
    if not isinstance(token, str) or not token.isascii() or not room or room['expires'] < time.time() or not secrets.compare_digest(room[role], token):
        raise PermissionError('Room expired or access denied.')
    return room


def publish(room_id, token, text, request_key):
    if not isinstance(text, str) or not text.strip() or len(text) > 2000:
        raise ValueError('Message must contain 1–2000 characters.')
    if not isinstance(request_key, str) or not 1 <= len(request_key) <= 100:
        raise ValueError('A request key of 1–100 characters is required.')
    text = text.strip()
    with LOCK:
        room = access(room_id, token, 'speaker')
        previous = room['requests'].get(request_key)
        if previous:
            if previous['text'] != text:
                raise ValueError('Request key already belongs to different text.')
            return previous
        if len(room['messages']) >= 200:
            raise ValueError('Room message limit reached. Create a new room.')
        message = {'id': len(room['messages']) + 1, 'text': text}
        room['messages'].append(message)
        room['requests'][request_key] = message
        return message


def poll(room_id, token, role, after=0):
    with LOCK:
        room = access(room_id, token, role)
        if role == 'listener':
            room['listener_seen'] = time.time()
            return {'messages': room['messages'][after:], 'latest': len(room['messages'])}
        return {'listener_connected': time.time() - room['listener_seen'] < 8, 'received_through': room['ack']}


def acknowledge(room_id, token, message_id):
    with LOCK:
        room = access(room_id, token, 'listener')
        if type(message_id) is not int or not 0 <= message_id <= len(room['messages']):
            raise ValueError('Invalid message ID.')
        room['ack'] = max(room['ack'], message_id)
