"""Photon 2.0 outbound messaging. Never used for general computer tasks."""
import json
import os
from pathlib import Path
import re
import threading
import urllib.error
import urllib.request
import urllib.parse
from commands import default_path

API = 'https://api.photon.codes/v1'


def valid_id(value, prefix):
    return isinstance(value,str) and bool(re.fullmatch(r'pho_'+prefix+r'_[0-7][0-9a-hjkmnp-tv-z]{25}',value))


class PhotonConfigError(ValueError):
    pass


class PhotonUncertain(RuntimeError):
    pass


def credentials():
    path=Path(os.environ.get('PHOTON_CONFIG_FILE',str(default_path().parent/'photon.json')))
    try:
        data=json.loads(path.read_text())
        key=os.environ.get('PHOTON_API_KEY') or data.get('api_key','')
        placeholder='SET_LOCALLY_OR_USE_PHOTON_API_KEY_ENVIRONMENT_VARIABLE'
        if (not isinstance(key,str) or not 16 <= len(key) <= 4096 or
                any(char.isspace() for char in key) or key==placeholder or
                not valid_id(data.get('project_id'),'prj')):
            raise ValueError()
        return data,key
    except (OSError,ValueError,TypeError,AttributeError):
        raise PhotonConfigError('Photon 2.0 is not configured. Set up .silent/photon.json from photon.example.json; never paste keys into the browser or commit them.')


def settings():
    data,key=credentials()
    try:
        if not isinstance(data.get('contacts'),list) or not data['contacts']:
            raise ValueError()
        return data,key
    except (ValueError,TypeError):
        raise PhotonConfigError('Photon 2.0 is not configured. Set up .silent/photon.json from photon.example.json; never paste keys into the browser or commit them.')


def companion_settings():
    data,key=credentials()
    value=data.get('companion')
    try:
        if not isinstance(value,dict) or value.get('enabled') is not True:
            raise ValueError('The companion is disabled')
        if value.get('platform') != 'imessage':
            raise ValueError('The companion currently supports iMessage only')
        agent_id=value.get('agent_id')
        agent=value.get('agent_handle')
        senders=value.get('allowed_senders')
        if not valid_id(agent_id,'usr'):
            raise ValueError('Set companion.agent_id to the Photon agent User ID')
        if not isinstance(agent,str) or not agent.strip() or len(agent)>320:
            raise ValueError('Set companion.agent_handle')
        if not isinstance(senders,list) or not senders or any(not isinstance(s,str) or not s.strip() or len(s)>320 for s in senders):
            raise ValueError('Set one or more companion.allowed_senders')
        senders=[s.strip() for s in senders]
        if len(senders)!=len(set(senders)) or agent.strip() in senders:
            raise ValueError('Companion handles must be distinct')
        return data,key,{**value,'agent_id':agent_id,'agent_handle':agent.strip(),'allowed_senders':senders}
    except (ValueError,TypeError) as exc:
        raise PhotonConfigError(f'Photon companion is not configured: {exc}.') from exc


def status():
    try:
        data,_=settings()
        return {'configured':True,'contacts':len(data['contacts']),'version':'2.0'}
    except PhotonConfigError as exc:
        return {'configured':False,'reason':str(exc),'version':'2.0'}


def companion_status():
    try:
        _,_,config=companion_settings()
        return {'configured':True,'platform':config['platform'],
                'allowed_senders':len(config['allowed_senders']),'version':'2.0'}
    except PhotonConfigError as exc:
        return {'configured':False,'reason':str(exc),'version':'2.0'}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        return None


class PhotonClient:
    def __init__(self, companion=False):
        if companion:
            self.config,self.key,self.companion=companion_settings()
        else:
            self.config,self.key=settings()
            self.companion=None
        self.opener=urllib.request.build_opener(NoRedirect)

    def request(self,path,body=None,key=None):
        # Keep read requests as plain authenticated GETs. Photon/Cloudflare may
        # reject a body-specific Content-Type on GET, even though the same key
        # is valid when the endpoint is called with curl.
        headers={'Authorization':'Bearer '+self.key,
                 'Accept':'application/json',
                 'User-Agent':'SilentOS-Photon/1.0'}
        if body is not None:headers['Content-Type']='application/json'
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
            detail=''
            try:
                payload=json.loads(exc.read(4096))
                if isinstance(payload,dict):
                    for field in ('detail','message','error','title','code'):
                        value=payload.get(field)
                        if isinstance(value,str) and value.strip():
                            detail=': '+value.strip()[:300]
                            break
            except (OSError,ValueError,TypeError):
                pass
            raise PhotonConfigError(f'Photon rejected the request (HTTP {exc.code}{detail}); check channel, sender, contact, and account permissions.') from exc
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

    def list_companion_messages(self, created_since, page_token=None):
        if self.companion is None:
            raise PhotonConfigError('This Photon client was not configured for the companion')
        query={'createdSince':created_since,'direction':'received','order':'asc','pageSize':100,
               'platform':self.companion['platform']}
        if page_token:query['pageToken']=page_token
        _,result=self.request('/messages?'+urllib.parse.urlencode(query))
        if not isinstance(result.get('items'),list):
            raise PhotonConfigError('Photon returned an invalid message list')
        token=result.get('nextPageToken')
        if token is not None and not isinstance(token,str):
            raise PhotonConfigError('Photon returned an invalid page token')
        return result['items'],token

    def companion_incoming(self, item):
        """Validate one Photon snapshot and return only the fields the companion uses."""
        if self.companion is None or not isinstance(item,dict):return None
        sender=item.get('sentBy');receiver=item.get('receivedBy');addressed=item.get('addressedTo')
        space=item.get('space');content=item.get('content')
        if item.get('platform')!='imessage' or item.get('status')!='received':return None
        if not all(isinstance(value,dict) for value in (sender,space,content)):return None
        if sender.get('kind')!='human' or sender.get('handle') not in self.companion['allowed_senders']:return None
        agent_id=self.companion['agent_id']
        if receiver is not None and (not isinstance(receiver,dict) or receiver.get('kind')!='agent' or
                receiver.get('id')!=agent_id or receiver.get('handle')!=self.companion['agent_handle']):return None
        if addressed is not None and (not isinstance(addressed,dict) or addressed.get('kind')!='agent' or
                addressed.get('id')!=agent_id or addressed.get('handle')!=self.companion['agent_handle']):return None
        participants=space.get('participantIds')
        if sender.get('id')==agent_id or space.get('kind')!='direct' or space.get('platform')!='imessage' or \
                not isinstance(participants,list) or set(participants)!={sender.get('id'),agent_id}:return None
        if content.get('type')!='text' or content.get('format')!='plain':return None
        fields={'id':item.get('id'),'space_id':space.get('id'),'sender_id':sender.get('id'),
                'agent_id':agent_id,'sender_handle':sender.get('handle'),
                'platform':'imessage','text':content.get('text'),'created_at':item.get('createdAt')}
        try:
            prefixes={'id':'msg','space_id':'spc','sender_id':'usr','agent_id':'usr'}
            if any(not valid_id(fields[name],prefix) for name,prefix in prefixes.items()):return None
            if not all(isinstance(fields[name],str) and fields[name].strip() for name in ('text','created_at')):return None
        except (TypeError,AttributeError):return None
        return fields

    def send_companion_reply(self, incoming):
        if self.companion is None:
            raise PhotonConfigError('This Photon client was not configured for the companion')
        _,space=self.request('/spaces/'+incoming['space_id'])
        participants=space.get('participantIds')
        if space.get('platform')!='imessage' or space.get('kind')!='direct' or not isinstance(participants,list) or \
                set(participants)!={incoming['sender_id'],incoming['agent_id']} or \
                incoming['sender_id']==incoming['agent_id']:
            raise PhotonConfigError('Photon conversation identity/participants changed. No reply was sent.')
        code,result=self.request('/messages',{'spaceId':incoming['space_id'],'senderId':incoming['agent_id'],
                         'parentMessageId':incoming['id'],
                         'content':{'type':'text','format':'plain','text':incoming['reply']}},
                         'silentos-companion-reply:'+incoming['id'])
        if code!=202 or not valid_id(result.get('id'),'msg'):
            raise PhotonUncertain('Photon did not return the expected accepted reply ID. Inspect its dashboard before retrying.')
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
