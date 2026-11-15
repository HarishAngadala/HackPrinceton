from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from companion import DeepAgentEngine, process_approved, process_inbound, process_task
from companion_store import CompanionStore
import photon


def ident(kind,number=1):
    return 'pho_'+kind+'_'+'0'*25+str(number)


class CompanionTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.store=CompanionStore(Path(self.folder.name)/'companion.sqlite3')
        self.incoming={'id':ident('msg'),'space_id':ident('spc'),'sender_id':ident('usr',1),
            'agent_id':ident('usr',2),'sender_handle':'+15555550123','platform':'imessage',
            'text':'Can you help me plan tomorrow?','created_at':'2026-11-14T23:00:00Z'}

    def tearDown(self):self.folder.cleanup()

    def test_draft_requires_approval_and_is_idempotent(self):
        first=self.store.ingest(self.incoming)
        self.assertEqual(first['id'],self.store.ingest(self.incoming)['id'])
        claimed=self.store.claim_for_draft();self.assertEqual(claimed['status'],'processing')
        draft=self.store.save_draft(claimed['id'],claimed['claim_token'],'Here is a plan.')
        self.assertEqual(draft['status'],'draft');self.assertIsNone(self.store.claim_for_send())
        approved=self.store.approve(draft['id'],'Edited approved reply')
        self.assertEqual(approved['status'],'approved')
        outgoing=self.store.claim_for_send();self.assertEqual(outgoing['reply'],'Edited approved reply')
        sent=self.store.mark_sent(outgoing['id'],outgoing['claim_token'],ident('msg',2))
        self.assertEqual(sent['status'],'accepted');self.assertEqual(sent['external_id'],ident('msg',2))

    def test_worker_heartbeat_reports_photon_mode(self):
        self.assertFalse(self.store.runtime_status()['worker_active'])
        self.store.heartbeat(True);status=self.store.runtime_status()
        self.assertTrue(status['worker_active']);self.assertTrue(status['worker_photon_enabled'])

    def test_only_definitive_blocks_can_be_retried(self):
        self.store.ingest(self.incoming);claimed=self.store.claim_for_draft()
        blocked=self.store.block_draft(claimed['id'],claimed['claim_token'],'model unavailable')
        self.assertEqual(self.store.retry_blocked(blocked['id'])['status'],'received')
        claimed=self.store.claim_for_draft();self.store.save_draft(claimed['id'],claimed['claim_token'],'reply')
        self.store.approve(claimed['id']);outgoing=self.store.claim_for_send()
        self.store.block_send(outgoing['id'],outgoing['claim_token'],'configuration rejected')
        self.assertEqual(self.store.retry_blocked(outgoing['id'])['status'],'draft')
        with self.assertRaises(ValueError):self.store.retry_blocked(outgoing['id'])

    def test_deepagent_factory_and_inbound_draft(self):
        class Agent:
            def invoke(self,payload):
                self.payload=payload
                return {'messages':[SimpleNamespace(content='A concise proposed reply')]}
        agent=Agent()
        engine=DeepAgentEngine(SimpleNamespace(recent=lambda:[]),model='test:model',
                               factory=lambda **kwargs:agent)
        self.store.ingest(self.incoming)
        self.assertTrue(process_inbound(self.store,engine))
        item=self.store.list()[0]
        self.assertEqual(item['status'],'draft');self.assertEqual(item['reply'],'A concise proposed reply')
        self.assertFalse(process_inbound(self.store,engine))

    def test_execute_task_never_claims_unverified_completion(self):
        class Client:
            def __init__(self,answer):self.answer=answer;self.reports=[]
            def claim(self):
                if hasattr(self,'claimed'):return None
                self.claimed=True;return {'id':'task','claim_token':'token','task':'Open an app','mode':'execute'}
            def report(self,*args):self.reports.append(args)
        class Engine:
            def __init__(self,answer):self.answer=answer
            def respond(self,*args):return self.answer
        for answer,expected in [('COMPLETED: answer produced','completed'),
                                ('BLOCKED: HeyClicky must open the app','blocked'),
                                ('I opened it','blocked')]:
            client=Client(answer);self.assertTrue(process_task(client,Engine(answer)))
            self.assertEqual(client.reports[0][2],expected)

    def test_photon_validation_and_approved_send(self):
        config={'project_id':ident('prj')};companion={'enabled':True,'platform':'imessage',
            'agent_id':ident('usr',2),'agent_handle':'+15555550999','allowed_senders':['+15555550123']}
        with patch.object(photon,'companion_settings',return_value=(config,'pho_sk_test',companion)):
            client=photon.PhotonClient(companion=True)
        raw={'id':ident('msg'),'platform':'imessage','status':'received','createdAt':self.incoming['created_at'],
             'sentBy':{'id':ident('usr',1),'kind':'human','handle':'+15555550123','platform':'imessage'},
             'receivedBy':{'id':ident('usr',2),'kind':'agent','handle':'+15555550999','platform':'imessage'},
             'space':{'id':ident('spc'),'kind':'direct','platform':'imessage',
                      'participantIds':[ident('usr',1),ident('usr',2)]},
             'content':{'type':'text','format':'plain','text':'hello'}}
        parsed=client.companion_incoming(raw);self.assertEqual(parsed['text'],'hello')
        del raw['receivedBy'];self.assertEqual(client.companion_incoming(raw)['agent_id'],ident('usr',2))
        raw['sentBy']['handle']='+15555550000';self.assertIsNone(client.companion_incoming(raw))

        calls=[]
        client.request=lambda path,body=None,key=None:(calls.append((path,body,key)) or
            ((200,{'platform':'imessage','kind':'direct','participantIds':[ident('usr',1),ident('usr',2)]})
             if body is None else (202,{'id':ident('msg',2)})))
        self.assertEqual(client.send_companion_reply({**self.incoming,'reply':'Approved response'}),ident('msg',2))
        self.assertEqual(calls[0][0],'/spaces/'+ident('spc'))
        self.assertEqual(calls[1][1]['parentMessageId'],ident('msg'))

        self.store.ingest(self.incoming);claimed=self.store.claim_for_draft()
        self.store.save_draft(claimed['id'],claimed['claim_token'],'Approved response')
        self.store.approve(claimed['id'])
        class Sender:
            def send_companion_reply(self,item):
                self.item=item;return ident('msg',2)
        sender=Sender();self.assertTrue(process_approved(self.store,sender))
        self.assertEqual(sender.item['id'],self.incoming['id']);self.assertEqual(self.store.list()[0]['status'],'accepted')


if __name__=='__main__':unittest.main()
