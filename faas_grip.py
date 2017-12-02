import os
import sys
from base64 import b64encode, b64decode
from struct import pack
import threading
import json
import types
import six
from pubcontrol import Item
from gripcontrol import GripPubControl, WebSocketEvent, WebSocketContext, \
	parse_grip_uri, decode_websocket_events, encode_websocket_events

is_python3 = sys.version_info >= (3,)

# The PubControl instance and lock used for synchronization.
_pubcontrol = None
_lock = threading.Lock()

def _is_basestring_instance(instance):
	try:
		if isinstance(instance, basestring):
			return True
	except NameError:
		if isinstance(instance, str):
			return True
	return False

def _get_proxies():
	proxies = []
	grip_proxies = os.environ.get('GRIP_PROXIES')
	if grip_proxies:
		proxies.extend(json.loads(grip_proxies))
	grip_url = os.environ.get('GRIP_URL')
	if grip_url:
		proxies.append(parse_grip_uri(grip_url))
	return proxies

def _get_pubcontrol():
	global _pubcontrol
	_lock.acquire()
	if _pubcontrol is None:
		_pubcontrol = GripPubControl()
		_pubcontrol.apply_grip_config(_get_proxies())
	_lock.release()
	return _pubcontrol

def _get_prefix():
	return os.environ.get('GRIP_PREFIX', '')

def get_pubcontrol():
	return _get_pubcontrol()

def publish(channel, formats, id=None, prev_id=None, blocking=True, callback=None, meta={}):
	pub = _get_pubcontrol()
	pub.publish(_get_prefix() + channel,
		Item(formats, id=id, prev_id=prev_id, meta=meta),
		blocking=blocking,
		callback=callback)

def lambda_websocket_to_response(wscontext):
	# meta to remove?
	meta_remove = set()
	for k, v in six.iteritems(wscontext.orig_meta):
		found = False
		for nk, nv in wscontext.meta:
			if nk.lower() == k:
				found = True
				break
		if not found:
			meta_remove.add(k)

	# meta to set?
	meta_set = {}
	for k, v in six.iteritems(wscontext.meta):
		lname = k.lower()
		need_set = True
		for ok, ov in wscontext.orig_meta:
			if lname == ok and v == ov:
				need_set = False
				break
		if need_set:
			meta_set[lname] = v

	events = []
	if wscontext.accepted:
		events.append(WebSocketEvent('OPEN'))
	events.extend(wscontext.out_events)
	if wscontext.closed:
		events.append(WebSocketEvent('CLOSE', pack('>H', wscontext.out_close_code)))

	headers = {'Content-Type': 'application/websocket-events'}
	if wscontext.accepted:
		headers['Sec-WebSocket-Extensions'] = 'grip'
	for k in meta_remove:
		headers['Set-Meta-' + k] = ''
	for k, v in six.iteritems(meta_set):
		headers['Set-Meta-' + k] = v

	body = encode_websocket_events(events)

	return {
		'isBase64Encoded': True,
		'statusCode': 200,
		'headers': headers,
		'body': b64encode(body)
	}

def lambda_get_websocket(event):
	lower_headers = {}
	for k, v in six.iteritems(event.get('headers', {})):
		lower_headers[k.lower()] = v

	content_type = lower_headers.get('content-type')
	if content_type:
		at = content_type.find(';')
		if at != -1:
			content_type = content_type[:at].strip()

	if event['httpMethod'] != 'POST' or content_type != 'application/websocket-events':
		raise ValueError('request does not seem to be a websocket-over-http request')

	cid = lower_headers.get('connection-id')

	meta = {}
	for k, v in six.iteritems(lower_headers):
		if k.startswith('meta-'):
			meta[k[5:]] = v

	# read body as binary
	if event.get('isBase64Encoded'):
		body = b64decode(event['body'])
	else:
		body = event['body']

	if is_python3:
		if isinstance(body, str):
			body = body.encode('utf-8')
	else:
		if isinstance(body, unicode):
			body = body.encode('utf-8')

	events = decode_websocket_events(body)

	wscontext = WebSocketContext(cid, meta, events, grip_prefix=_get_prefix())

	wscontext.to_response = types.MethodType(lambda_websocket_to_response, wscontext)

	return wscontext
