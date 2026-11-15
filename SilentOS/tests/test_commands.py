from concurrent.futures import ThreadPoolExecutor
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from commands import CommandStore, parse_command
from heyclicky_mcp import serve, call_tool


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / 'state' / 'commands.sqlite3'
        self.store = CommandStore(self.path)

    def tearDown(self):
        self.folder.cleanup()

    def enqueue(self, key='one', mode='draft', **extra):
        return self.store.enqueue({'request_key':key,'mode':mode,'transcript':'Send Alex on WhatsApp saying hello',
                                   'app':'whatsapp','recipient':'Alex','message':'hello',**extra})

    def test_parse_explicit_commands_without_rewriting_body(self):
        for phrase, app in [('Send Alex on WhatsApp saying ', 'whatsapp'), ('Send a message to Alex via iMessage: ', 'imessage'), ('Text Alex using SMS saying ', 'sms')]:
            result = parse_command(phrase + "Very very good. Don't change this!")
            self.assertEqual(result['app'], app)
            self.assertEqual(result['recipient'], 'Alex')
            self.assertEqual(result['message'], "Very very good. Don't change this!")
        for phrase in ['tell Alex hello','send Alex hello','Send Alex on Telegram: hi','Send Alex on WhatsApp']:
            self.assertFalse(parse_command(phrase)['parsed'])
        with self.assertRaises(ValueError):
            parse_command('')

    def test_idempotency_and_restart(self):
        first = self.enqueue()
        self.assertEqual(first['id'], self.enqueue()['id'])
        self.assertEqual(len(CommandStore(self.path).list()), 1)
        with self.assertRaisesRegex(ValueError, 'different command'):
            self.enqueue(message='different')
        self.assertNotIn('claim_token', first)

    def test_concurrent_claim_once_and_never_reclaim(self):
        self.enqueue()
        self.enqueue('two')
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(lambda _: CommandStore(self.path).claim(), range(6)))
        claimed = [r for r in results if r is not None]
        self.assertEqual(len(claimed), 1)
        self.assertIsNone(CommandStore(self.path).claim())
        self.assertTrue(claimed[0]['claim_token'])
        self.assertNotIn('claim_token', self.store.list()[0])
        self.store.resolve_uncertain(claimed[0]['id'])
        self.assertIsNotNone(self.store.claim())

    def test_result_token_draft_and_replay_guards(self):
        first = self.enqueue()
        c = self.store.claim()
        with self.assertRaisesRegex(ValueError, 'token'):
            self.store.report(c['id'],'wrong','prepared','draft visible')
        with self.assertRaisesRegex(ValueError, 'Draft'):
            self.store.report(c['id'],c['claim_token'],'sent','oops')
        result = self.store.report(c['id'],c['claim_token'],'prepared','draft visible')
        self.assertEqual(result['status'], 'prepared')
        self.assertEqual(result,self.store.report(c['id'],c['claim_token'],'prepared','draft visible'))
        with self.assertRaises(ValueError):
            self.store.report(c['id'],c['claim_token'],'blocked','changed outcome')
        self.assertIsNone(self.store.claim())
        self.assertEqual(first['id'],c['id'])

    def test_cancel_and_queue_bounds(self):
        c = self.enqueue()
        self.store.cancel(c['id'])
        self.assertIsNone(self.store.claim())
        for i in range(25):
            self.enqueue(str(i))
        with self.assertRaisesRegex(ValueError,'Queue full'):
            self.enqueue('overflow')
        c = self.store.claim()
        with self.assertRaises(ValueError):
            self.store.cancel(c['id'])
        self.store.report(c['id'],c['claim_token'],'blocked','recipient ambiguous, no send attempted')
        self.enqueue('overflow')

    def test_validation(self):
        for extra in [{'app':'slack'},{'mode':'automatic'},{'recipient':''},{'message':''},{'recipient':'a\nb'}]:
            with self.assertRaises(ValueError):
                self.enqueue(**extra)

    def test_malformed_command_ids_are_validation_errors(self):
        for bad in [None, {}, [], '']:
            for operation in [self.store.cancel, self.store.resolve_uncertain]:
                with self.assertRaises(ValueError):
                    operation(bad)
            with self.assertRaises(ValueError):
                self.store.report(bad,'token','blocked','not attempted')

    def test_mcp_protocol_and_errors(self):
        messages = [
            {'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-06-18'}},
            {'jsonrpc':'2.0','method':'notifications/initialized'},
            {'jsonrpc':'2.0','id':2,'method':'tools/list'},
            {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'silentos_claim_next_command','arguments':{}}},
            {'jsonrpc':'2.0','id':4,'method':'tools/call','params':{'name':'silentos_claim_next_command','arguments':{'wait_seconds':True}}},
            {'jsonrpc':'2.0','id':5,'method':'unknown'}]
        out=io.StringIO();serve(self.store,io.StringIO('\n'.join(json.dumps(m) for m in messages)),out)
        replies=[json.loads(line) for line in out.getvalue().splitlines()]
        self.assertEqual(len(replies),5)
        self.assertEqual(len(replies[1]['result']['tools']),3)
        self.assertIsNone(json.loads(replies[2]['result']['content'][0]['text'])['command'])
        self.assertTrue(replies[3]['result']['isError'])
        self.assertEqual(replies[4]['error']['code'],-32601)



if __name__ == '__main__':
    unittest.main()
