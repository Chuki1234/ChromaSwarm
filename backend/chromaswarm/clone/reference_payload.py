"""Lossless transport for the large DevTools snapshot carried by a Clone checkpoint."""
from __future__ import annotations

import base64
import json
import zlib

ENCODING = 'deflate-json-v1'
MAX_BYTES = 8 * 1024 * 1024


def pack(value: dict) -> dict:
    if not value or value.get('encoding') == ENCODING:
        return value
    raw = json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return {'encoding': ENCODING, 'asset_count': len(value.get('assets', [])),
            'data': base64.b64encode(zlib.compress(raw)).decode('ascii')}


def unpack(value: dict) -> dict:
    if value.get('encoding') != ENCODING:
        return value  # Existing sessions keep their uncompressed snapshot.
    encoded = value.get('data', '')
    if len(encoded) > MAX_BYTES:
        raise ValueError('reference snapshot is too large')
    decoder = zlib.decompressobj()
    raw = decoder.decompress(base64.b64decode(encoded, validate=True), MAX_BYTES + 1)
    if len(raw) > MAX_BYTES or not decoder.eof:
        raise ValueError('reference snapshot exceeds the decoded size limit')
    result = json.loads(raw)
    if not isinstance(result, dict):
        raise ValueError('reference snapshot must contain an object')
    return result
