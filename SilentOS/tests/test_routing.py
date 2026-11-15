import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import unittest
from unittest.mock import patch
from test_backend import HTTPTestCase
from commands import CommandStore, route_task
import photon
import server


def ident(kind, number=1):
    return 'pho_'+kind+'_'+'0'*25+str(number)


class RoutingTests(HTTPTestCase):
    def post(self,path,data):
        return self.call(path,json.dumps(data).encode(),{'Content-Type':'application/json','X-SilentOS-Token':server.TOKEN})

    def test_text_api_and_real_mcp_process(self):
        message={'app':'imessage','recipient':'Test','message':'hello','mode':'draft','transcript':'hello','request_key':'message'}
        self.assertEqual(self.post('/api/commands',message)[0],200)
        code,body=self.post('/api/tasks',{'text':'Open Downloads','request_key':'task','mode':'execute'})
        self.assertEqual(code,200);task=json.loads(body)
        self.assertEqual(task['provider'],'heyclicky')
        proc=subprocess.Popen([sys.executable,str(Path(__file__).resolve().parents[1]/'heyclicky_mcp.py'),'--api-url',self.url],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        def rpc(number,method,params=None):
            proc.stdin.write(json.dumps({'jsonrpc':'2.0','id':number,'method':method,'params':params or {}})+'\n');proc.stdin.flush()
            result=json.loads(proc.stdout.readline())['result']
            return json.loads(result['content'][0]['text']) if 'content' in result else result
        try:
            rpc(1,'initialize')
            listed=rpc(2,'tools/call',{'name':'silentos_list_commands','arguments':{}})['commands']
            self.assertEqual([t['id'] for t in listed],[task['id']])
            claimed=rpc(3,'tools/call',{'name':'silentos_claim_next_command','arguments':{}})['command']
            self.assertEqual(claimed['task'],'Open Downloads')
            result=rpc(4,'tools/call',{'name':'silentos_report_result','arguments':{'id':claimed['id'],'claim_token':claimed['claim_token'],'outcome':'completed','detail':'simulated result for transport test'}})
            self.assertEqual(result['status'],'completed')
        finally:
            proc.stdin.close();proc.wait(timeout=5);proc.stdout.close();proc.stderr.close()
        photon_item=server.command_store().claim('photon')
        self.assertEqual(photon_item['kind'],'message')
        self.assertEqual(self.post('/api/tasks/result',{'id':photon_item['id'],'claim_token':photon_item['claim_token'],'outcome':'prepared','detail':'wrong route'})[0],400)

    def test_route_guards_and_unknown_input(self):
        self.assertEqual(route_task('Open my latest presentation')['provider'],'heyclicky')
        self.assertEqual(route_task('Send Test on WhatsApp saying hello')['provider'],'photon')
        self.assertFalse(route_task('Text Test something')['parsed'])
        with self.assertRaises(ValueError):route_task('Send Test on iMessage saying hello','task')
        self.assertEqual(self.post('/api/tasks',{'text':'Email Test hello','request_key':'bad'})[0],400)
        self.assertEqual(self.call('/api/tasks')[0],403)

    def test_workers_claim_separate_providers(self):
        self.post('/api/tasks',{'text':'Open Downloads','request_key':'one'})
        self.post('/api/commands',{'app':'sms','recipient':'Test','message':'hello','mode':'draft','transcript':'hello','request_key':'two'})
        store=server.command_store();task=store.claim('heyclicky');msg=store.claim('photon')
        self.assertEqual(task['kind'],'task');self.assertEqual(msg['kind'],'message')
        self.assertIsNone(store.claim('heyclicky'));self.assertIsNone(store.claim('photon'))
        with self.assertRaises(ValueError):store.report(task['id'],task['claim_token'],'accepted','wrong task outcome')

    def test_legacy_database_is_migrated_but_not_dispatched(self):
        path=Path(self.folder.name)/'legacy.sqlite3'
        with sqlite3.connect(path) as db:
            db.execute("CREATE TABLE commands (id TEXT PRIMARY KEY, request_key TEXT UNIQUE NOT NULL,payload TEXT NOT NULL,status TEXT NOT NULL,created REAL NOT NULL,updated REAL NOT NULL,claim_token TEXT,detail TEXT NOT NULL DEFAULT '')")
            db.execute("INSERT INTO commands VALUES ('old','old',?,'queued',1,1,NULL,'')",(json.dumps({'app':'sms','recipient':'Test','message':'old','transcript':'old','mode':'send'}),))
        store=CommandStore(path);self.assertEqual(store.list()[0]['provider'],'legacy')
        self.assertIsNone(store.claim('photon'));self.assertIsNone(store.claim('heyclicky'))


class PhotonTests(HTTPTestCase):
    def message(self,mode='send'):
        return server.command_store().enqueue({'app':'imessage','recipient':'Test','message':'hello','mode':mode,'transcript':'hello','request_key':'test'})

    def test_preview_never_contacts_photon_and_missing_setup_blocks_send(self):
        self.message('draft')
        with patch.object(photon,'PhotonClient',side_effect=AssertionError('must not contact')):
            photon.process_one(server.command_store())
        self.assertEqual(server.command_store().list()[0]['status'],'prepared')
        store=CommandStore(Path(self.folder.name)/'other.sqlite3');store.enqueue({'app':'sms','recipient':'Test','message':'hello','mode':'send','transcript':'hello','request_key':'send'})
        def missing():raise photon.PhotonConfigError('Not configured')
        photon.process_one(store,missing);self.assertEqual(store.list()[0]['status'],'blocked')

    def client(self):
        data={'project_id':ident('prj'),'contacts':[{'name':'Test','app':'imessage','platform':'imessage','space_id':ident('spc'),'sender_id':ident('usr',1),'recipient_id':ident('usr',2)}]}
        with patch.object(photon,'settings',return_value=(data,'pho_sk_test')):return photon.PhotonClient()

    def test_photon_contract_identity_guard_and_no_retry(self):
        c=self.message();client=self.client();calls=[]
        def request(path,body=None,key=None):
            calls.append((path,body,key))
            if body is None:return 200,{'platform':'imessage','kind':'direct','participantIds':[ident('usr',1),ident('usr',2)]}
            return 202,{'id':ident('msg')}
        client.request=request
        photon.process_one(server.command_store(),lambda:client)
        result=server.command_store().get(c['id']);self.assertEqual(result['status'],'accepted');self.assertEqual(result['external_id'],ident('msg'))
        self.assertEqual(calls[1][1]['content']['text'],'hello');self.assertEqual(calls[1][2],'silentos-'+c['id'])
        self.assertFalse(photon.process_one(server.command_store(),lambda:client));self.assertEqual(len(calls),2)
        bad=self.client();bad.request=lambda *args:(200,{'platform':'sms','kind':'direct','participantIds':[]})
        with self.assertRaises(photon.PhotonConfigError):bad.send(c)

    def test_uncertain_send_is_terminal(self):
        self.message()
        class Uncertain:
            def send(self,c):raise photon.PhotonUncertain('Lost response')
        photon.process_one(server.command_store(),Uncertain)
        self.assertEqual(server.command_store().list()[0]['status'],'uncertain')
        self.assertFalse(photon.process_one(server.command_store(),Uncertain))


if __name__=='__main__':unittest.main()
