"""Dependency-free MCP stdio connector. Launched by HeyClicky, not the browser."""
import argparse
import json
import sys
import time
from commands import INSTRUCTIONS
from silentos_api import SilentOSClient


def schema(properties=None, required=None):
    return {'type': 'object', 'properties': properties or {}, 'required': required or [], 'additionalProperties': False}


TEXT = {'type': 'string', 'minLength': 1}
TOOLS = [
    {'name': 'silentos_list_commands', 'description': 'Read general task text and status from the SilentOS HTTP API. Photon messages are excluded. Does not execute anything.',
     'inputSchema': schema(), 'annotations': {'readOnlyHint': True}},
    {'name': 'silentos_claim_next_command', 'description': 'Atomically claim one general task from the SilentOS HTTP API. Returns null if empty or another command is already claimed. Never reclaims old work. Optional long poll up to 20 seconds. Follow execution_instructions, mode, and host approval policy.',
     'inputSchema': schema({'wait_seconds': {'type': 'integer', 'minimum': 0, 'maximum': 20}})},
    {'name': 'silentos_report_result', 'description': 'Report what you observed after handling a claimed command. completed=verified general task result, reviewed=plan only, blocked=not attempted, uncertain=effects cannot be verified. Messaging is handled separately by Photon.',
     'inputSchema': schema({'id': TEXT, 'claim_token': TEXT, 'outcome': {'type': 'string', 'enum': ['completed','reviewed','blocked','uncertain']},
                            'detail': {'type': 'string', 'minLength': 1, 'maxLength': 1000}}, ['id','claim_token','outcome','detail'])}
]


def call_tool(store, name, args):
    tool = next((t for t in TOOLS if t['name'] == name), None)
    if tool is None:
        raise ValueError('Unknown tool')
    shape = tool['inputSchema']
    if not isinstance(args, dict) or set(args) - set(shape['properties']) or set(shape['required']) - set(args):
        raise ValueError('Invalid tool arguments')
    for key, value in args.items():
        spec = shape['properties'][key]
        if spec['type'] == 'string' and (not isinstance(value, str) or not spec.get('minLength', 0) <= len(value) <= spec.get('maxLength', 10000)):
            raise ValueError(f'Invalid {key}')
    if name == 'silentos_list_commands':
        return {'commands': store.list()}
    if name == 'silentos_claim_next_command':
        wait = args.get('wait_seconds', 0)
        if type(wait) is not int or not 0 <= wait <= 20:
            raise ValueError('wait_seconds must be an integer between 0 and 20')
        deadline = time.monotonic() + wait
        while True:
            command = store.claim()
            if command is not None or time.monotonic() >= deadline:
                return {'command': command, 'execution_instructions': INSTRUCTIONS,
                        'note': 'No automatic wakeup. An active HeyClicky job must call this tool.'}
            time.sleep(min(.25, max(0, deadline-time.monotonic())))
    return store.report(args['id'], args['claim_token'], args['outcome'], args['detail'])


def serve(store, source, target):
    initialized = False
    for line in source:
        request = None
        try:
            if len(line) > 100000:
                raise ValueError('Request too large')
            request = json.loads(line)
        except (ValueError, UnicodeError):
            response = {'jsonrpc': '2.0', 'id': None, 'error': {'code': -32700, 'message': 'Invalid JSON request'}}
        else:
            if not isinstance(request, dict) or request.get('jsonrpc') != '2.0' or not isinstance(request.get('method'), str):
                response = {'jsonrpc': '2.0', 'id': None, 'error': {'code': -32600, 'message': 'Invalid JSON-RPC request'}}
            elif 'id' not in request:
                continue  # Notifications never receive responses.
            else:
                response = {'jsonrpc': '2.0', 'id': request['id']}
                method, params = request['method'], request.get('params', {})
                try:
                    if not isinstance(params, dict):
                        raise ValueError('params must be an object')
                    if method == 'initialize':
                        version = params.get('protocolVersion')
                        version = version if version in ('2024-11-05','2025-03-26','2025-06-18') else '2025-06-18'
                        response['result'] = {'protocolVersion': version, 'capabilities': {'tools': {}},
                                              'serverInfo': {'name':'silentos','version':'2.0.0'}, 'instructions': INSTRUCTIONS}
                        initialized = True
                    elif method == 'ping':
                        response['result'] = {}
                    elif not initialized:
                        raise ValueError('Initialize the connector first')
                    elif method == 'tools/list':
                        response['result'] = {'tools': TOOLS}
                    elif method == 'tools/call':
                        try:
                            result = call_tool(store, params.get('name'), params.get('arguments', {}))
                            response['result'] = {'content': [{'type':'text','text':json.dumps(result,ensure_ascii=False)}], 'isError':False}
                        except ValueError as exc:
                            response['result'] = {'content': [{'type':'text','text':str(exc)}], 'isError':True}
                    else:
                        response['error'] = {'code': -32601, 'message': 'Method not found'}
                except ValueError as exc:
                    response['error'] = {'code': -32602, 'message': str(exc)}
                except Exception:
                    response['error'] = {'code': -32603, 'message': 'Local command storage unavailable'}
        target.write(json.dumps(response,ensure_ascii=False) + '\n')
        target.flush()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--api-url', default=None, help='SilentOS localhost API origin; defaults to SILENTOS_API_URL or http://127.0.0.1:8000')
    args = parser.parse_args()
    serve(SilentOSClient(args.api_url), sys.stdin, sys.stdout)
