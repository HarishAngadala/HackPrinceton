"""Local HTTP client used by the HeyClicky MCP connector (text in, results out)."""
import json
import os
import urllib.error
import urllib.request
from urllib.parse import urlparse


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        return None


class SilentOSClient:
    def __init__(self, base_url=None):
        self.opener = urllib.request.build_opener(NoRedirect)
        self.url = (base_url or os.environ.get('SILENTOS_API_URL','http://127.0.0.1:8000')).rstrip('/')
        parsed = urlparse(self.url)
        if parsed.scheme != 'http' or parsed.hostname not in ('localhost','127.0.0.1') or parsed.path or parsed.query or parsed.fragment or parsed.username:
            raise ValueError('SilentOS API must be an HTTP localhost/127.0.0.1 origin')

    def request(self, path, data=None):
        try:
            # Obtain the current per-server token on every operation; never persist it.
            with self.opener.open(self.url+'/api/config',timeout=5) as response:
                token = json.load(response)['session_token']
            req = urllib.request.Request(self.url+path,
                data=None if data is None else json.dumps(data).encode(),
                headers={'Content-Type':'application/json','X-SilentOS-Token':token})
            with self.opener.open(req,timeout=10) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            try: detail=json.load(exc).get('error','SilentOS request rejected')
            except Exception: detail='SilentOS request rejected'
            raise ValueError(detail) from exc
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise ValueError('Cannot reach the SilentOS API. Start server.py and check --api-url. No operation was retried; inspect the queue before repeating.') from exc

    def list(self):
        return self.request('/api/tasks')['commands']

    def claim(self):
        return self.request('/api/tasks/next',{})['command']

    def report(self, command_id, token, outcome, detail):
        return self.request('/api/tasks/result',{'id':command_id,'claim_token':token,'outcome':outcome,'detail':detail})
