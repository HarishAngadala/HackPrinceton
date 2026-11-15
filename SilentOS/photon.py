"""Photon 2.0 outbound messaging. Never used for general computer tasks."""
import json
import os
from pathlib import Path
import re
import threading
import urllib.error
import urllib.request
from commands import default_path

API = 'https://api.photon.codes/v1'


def valid_id(value, prefix):
    return isinstance(value,str) and bool(re.fullmatch(r'pho_'+prefix+r'_[0-7][0-9a-hjkmnp-tv-z]{25}',value))


class PhotonConfigError(ValueError):
    pass


class PhotonUncertain(RuntimeError):
    pass


def settings():
    path=Path(os.environ.get('PHOTON_CONFIG_FILE',str(default_path().parent/'photon.json')))
    try:
        data=json.loads(path.read_text())
        key=os.environ.get('PHOTON_API_KEY') or data.get('api_key','')
        if not isinstance(key,str) or not key.startswith(('pho_sk_','pho_ask_')) or not valid_id(data.get('project_id'),'prj'):
            raise ValueError()
        if not isinstance(data.get('contacts'),list) or not data['contacts']:
            raise ValueError()
        return data,key
    except (OSError,ValueError,TypeError,AttributeError):
        raise PhotonConfigError('Photon 2.0 is not configured. Set up .silent/photon.json from photon.example.json; never paste keys into the browser or commit them.')


def status():
    try:
        data,_=settings()
        return {'configured':True,'contacts':len(data['contacts']),'version':'2.0'}
    except PhotonConfigError as exc:
        return {'configured':False,'reason':str(exc),'version':'2.0'}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        return None


class PhotonClient:
    def __init__(self):
        self.config,self.key=settings()
        self.opener=urllib.request.build_opener(NoRedirect)

    def request(self,path,body=None,key=None):
        headers={'Authorization':'Bearer '+self.key,'Content-Type':'application/json'}
        if key: headers['idempotency-key']=key
        req=urllib.request.Request(API+'/projects/'+self.config['project_id']+path,
                                   data=None if body is None else json.dumps(body).encode(),headers=headers)
        try:
            with self.opener.open(req,timeout=25) as response:
                data=json.load(response)
                if not isinstance(data,dict): raise ValueError('Invalid Photon response')
                return response.status,data
        except urllib.error.HTTPError as exc:
            if body is not None and exc.code>=500:
                raise PhotonUncertain('Photon returned a server error; send outcome is uncertain. Check its dashboard before retrying.') from exc
            raise PhotonConfigError(f'Photon rejected the request (HTTP {exc.code}); check channel, sender, contact, and account permissions.') from exc
        except (OSError,ValueError) as exc:
            if body is not None:
                raise PhotonUncertain('No usable Photon send response. Do not retry automatically; inspect its dashboard.') from exc
            raise PhotonConfigError('Unable to verify the Photon destination. No message was sent.') from exc

    def send(self,command):
        candidates=[c for c in self.config['contacts'] if isinstance(c,dict) and c.get('app')==command['app'] and
                    isinstance(c.get('name'),str) and c['name'].strip().casefold()==command['recipient'].strip().casefold()]
        if len(candidates)!=1: raise PhotonConfigError('Recipient must match exactly one configured Photon contact for this channel.')
        contact=candidates[0]
        for field,prefix in [('space_id','spc'),('sender_id','usr'),('recipient_id','usr')]:
            if not valid_id(contact.get(field),prefix): raise PhotonConfigError('Photon contact IDs are incomplete or invalid.')
        platform=contact.get('platform',command['app'])
        allowed={'imessage':{'imessage'},'sms':{'sms'},'whatsapp':{'whatsapp','whatsapp_business'}}
        if platform not in allowed[command['app']]: raise PhotonConfigError('Photon channel does not match the requested app.')
        _,space=self.request('/spaces/'+contact['space_id'])
        if space.get('platform')!=platform or space.get('kind')!='direct' or set(space.get('participantIds',[]))!={contact['sender_id'],contact['recipient_id']} or contact['sender_id']==contact['recipient_id']:
            raise PhotonConfigError('Photon conversation identity/participants do not match the configured recipient. No message was sent.')
        code,result=self.request('/messages',{'spaceId':contact['space_id'],'senderId':contact['sender_id'],
                         'content':{'type':'text','format':'plain','text':command['message']}},'silentos-'+command['id'])
        if code!=202 or not valid_id(result.get('id'),'msg'):
            raise PhotonUncertain('Photon did not return the expected accepted message ID. Inspect its dashboard before retrying.')
        return result['id']


def process_one(store,client_factory=PhotonClient):
    command=store.claim('photon')
    if not command:return False
    outcome='uncertain';detail='Photon processing interrupted; inspect queue before repeating.'
    try:
        if command['mode']=='draft':
            outcome='prepared';detail='Local message preview saved. Photon was not contacted and no message was sent.'
        else:
            message_id=client_factory().send(command)
            store.set_external_id(command['id'],message_id)
            outcome='accepted';detail='Photon accepted the message for asynchronous delivery. This is not a delivery receipt.'
    except PhotonConfigError as exc:
        outcome='blocked';detail=str(exc)
    except PhotonUncertain as exc:
        detail=str(exc)
    except Exception:
        detail='Unexpected Photon processing failure. Check the dashboard before repeating; nothing was automatically retried.'
    store.report(command['id'],command['claim_token'],outcome,detail)
    return True


def start_worker(store,stop_event):
    def run():
        while not stop_event.is_set():
            try: process_one(store)
            except Exception: pass  # A claimed item stays claimed; never replay after a crash.
            stop_event.wait(1)
    thread=threading.Thread(target=run,name='silentos-photon',daemon=True)
    thread.start()
    return thread
