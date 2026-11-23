import copy
import json
from pathlib import Path
import re
import os
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from careerflow import core, learning, training, training_web, workspace


LESSON={'topic':'Project handoffs','goal':'Write a handoff with an owner and observable next action',
        'explanation':'A useful handoff identifies the owner, next action and how completion is checked.',
        'exercise':'Rewrite an ambiguous handoff and explain your choices.',
        'hints':['Identify who owns the next action.','Define observable completion.'],
        'rubric':['Names an owner','Defines observable completion'],'resources':[]}


def review(outcome='pass'):
    return {'outcome':outcome,'feedback':'Inspected the written handoff against the criteria; no external tests run.',
            'criteria':[{'criterion':c,'met':outcome=='pass','feedback':'Observed in the artifact' if outcome=='pass' else 'Needs a more concrete statement'} for c in LESSON['rubric']],
            'next_topic':'Handle a delayed handoff'}


class TrainingTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);workspace.initialize(self.root)

    def ready(self):
        r=training.request(self.root,'Project handoffs',30,'Beginner')
        training.plan(self.root,r['id'],LESSON)
        return r['id']

    def test_complete_session_retries_preserve_attempts_and_claims(self):
        profile=(self.root/'data/profile.json').read_bytes()
        rid=self.ready()
        with self.assertRaises(ValueError):training.complete(self.root,rid,'Cannot complete a plan')
        training.start(self.root,rid)
        training.save_draft(self.root,rid,'My draft')
        self.assertEqual(training.get(self.root,rid)['session']['draft'],'My draft')
        training.attempt(self.root,rid,'First ambiguous handoff','Independent attempt')
        r=training.get(self.root,rid);first=self.root/r['session']['attempts'][0]['path'];original=first.read_bytes()
        with self.assertRaises(ValueError):learning.update(self.root,rid,'training','completed','No review',evidence=first)
        bad=review();bad['criteria'][0]['met']=False
        with self.assertRaises(ValueError):training.feedback(self.root,rid,bad)
        training.feedback(self.root,rid,review('retry'))
        with self.assertRaises(ValueError):training.complete(self.root,rid,'Cannot pass retry')
        training.start(self.root,rid)
        training.attempt(self.root,rid,'Owner: Alex. Completion: issue log contains accepted handoff.','Corrected attempt')
        training.feedback(self.root,rid,review())
        complete=training.complete(self.root,rid,'Reviewed and completed')
        self.assertEqual(complete['status'],'completed')
        self.assertEqual(complete['session']['phase'],'completed')
        self.assertEqual(len(complete['session']['attempts']),2)
        self.assertEqual(first.read_bytes(),original)
        self.assertEqual((self.root/'data/profile.json').read_bytes(),profile)
        self.assertEqual(learning.validate(self.root),[])
        with self.assertRaises(ValueError):training.start(self.root,rid)
        with self.assertRaises(ValueError):learning.update(self.root,rid,'training','paused','Cannot reopen completed work')

    def test_invalid_generation_and_review_do_not_advance_session(self):
        rid=training.request(self.root)['id']
        bad=copy.deepcopy(LESSON);bad['rubric']=[]
        with self.assertRaises(ValueError):training.plan(self.root,rid,bad)
        self.assertEqual(training.get(self.root,rid)['session']['phase'],'requested')
        training.plan(self.root,rid,LESSON)
        with self.assertRaises(ValueError):training.plan(self.root,rid,LESSON)
        with self.assertRaises(ValueError):training.feedback(self.root,rid,review())
        training.start(self.root,rid);training.attempt(self.root,rid,'Attempt','First try')
        wrong=review();wrong['criteria'].reverse()
        with self.assertRaises(ValueError):training.feedback(self.root,rid,wrong)
        self.assertEqual(training.get(self.root,rid)['session']['phase'],'submitted')

    def test_tampered_attempt_cannot_be_reviewed_or_completed(self):
        rid=self.ready();training.start(self.root,rid);training.attempt(self.root,rid,'Attempt','First')
        item=training.get(self.root,rid)['session']['attempts'][0]
        path=self.root/item['path'];original=path.read_bytes();path.write_text('Modified')
        with self.assertRaises(ValueError):training.feedback(self.root,rid,review())
        path.write_bytes(original);training.feedback(self.root,rid,review());path.write_text('Modified again')
        with self.assertRaises(ValueError):training.complete(self.root,rid,'No stale evidence')
        self.assertTrue(learning.validate(self.root))

    def test_paused_session_resumes_without_losing_draft_or_bypassing_review(self):
        rid=self.ready();training.start(self.root,rid);training.save_draft(self.root,rid,'Saved work')
        learning.update(self.root,rid,'training','paused','Candidate stopped for today')
        resumed=training.start(self.root,rid)
        self.assertEqual(resumed['session']['draft'],'Saved work')
        training.attempt(self.root,rid,'Owner and completion','Candidate work');training.feedback(self.root,rid,review())
        unrelated=self.root/'unrelated.md';unrelated.write_text('Unrelated artifact')
        with self.assertRaises(ValueError):learning.update(self.root,rid,'training','completed','Wrong artifact',evidence=unrelated)

    def test_queue_context_and_resume_are_shared_records(self):
        rid=training.request(self.root,minutes=15)['id']
        self.assertEqual(training.pending(self.root)[0]['id'],rid)
        context=training.context(self.root,rid)
        self.assertEqual(context['training']['session']['request']['minutes'],15)
        self.assertEqual(context['claims'],[])
        training.plan(self.root,rid,LESSON)
        self.assertEqual(training.pending(self.root),[])
        training.start(self.root,rid);training.attempt(self.root,rid,'Candidate text','Independent')
        self.assertEqual(training.pending(self.root)[0]['id'],rid)
        self.assertIn('Candidate text',training.context(self.root,rid)['attempts'][0]['text'])
        for minutes in (0,500,True):
            with self.assertRaises(ValueError):training.request(self.root,minutes=minutes)

    def test_launcher_from_a_checkout_with_an_older_engine(self):
        shadow=self.root/'old-checkout';(shadow/'careerflow').mkdir(parents=True)
        (shadow/'careerflow/__init__.py').write_text('')
        (shadow/'careerflow/__main__.py').write_text('raise SystemExit("Obsolete engine has no training-web command")')
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1',0));port=reservation.getsockname()[1]
        script=Path(__file__).resolve().parents[1]/'scripts/run_training.py'
        result=subprocess.run([sys.executable,str(script),'--root',str(self.root),'--port',str(port),'--no-browser'],
            cwd=shadow,capture_output=True,text=True,timeout=10)
        state=self.root/'.careerflow/training-web.json'
        if state.exists():self.addCleanup(os.kill,core.read(state)['pid'],signal.SIGTERM)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(training_web.health(port)['workspace'],str(self.root))


class TrainingWebTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);workspace.initialize(self.root)
        self.server=training_web.make_server(self.root,0)
        thread=threading.Thread(target=self.server.serve_forever,daemon=True);thread.start()
        def stop():self.server.shutdown();self.server.server_close();thread.join(timeout=2)
        self.addCleanup(stop)
        self.base='http://127.0.0.1:'+str(self.server.server_port)
        with urlopen(self.base) as r:
            self.html=r.read().decode();self.csp=r.headers['Content-Security-Policy']
        self.token=re.search('name="token" content="([^"]+)"',self.html)[1]

    def post(self,path,data,token=True,origin=None):
        headers={'Content-Type':'application/json'}
        if token:headers['X-Careerflow-Token']=self.token
        if origin:headers['Origin']=origin
        request=Request(self.base+'/api/'+path,json.dumps(data).encode(),headers=headers)
        with urlopen(request) as response:return json.load(response)

    def test_browser_agent_roundtrip_and_persistent_draft(self):
        rid=self.post('request',{'topic':'Project handoffs','minutes':30})['id']
        with core.locked(self.root):training.plan(self.root,rid,LESSON)
        request=Request(self.base+'/api/training?id='+rid,headers={'X-Careerflow-Token':self.token})
        with urlopen(request) as response:self.assertEqual(json.load(response)['session']['phase'],'ready')
        self.post('start',{'id':rid});self.post('draft',{'id':rid,'text':'Saved before refresh'})
        self.assertEqual(training.get(self.root,rid)['session']['draft'],'Saved before refresh')
        self.post('attempt',{'id':rid,'text':'Owner and observable completion'})
        with self.assertRaises(HTTPError):self.post('complete',{'id':rid})
        with core.locked(self.root):training.feedback(self.root,rid,review())
        self.assertEqual(self.post('complete',{'id':rid})['status'],'completed')
        self.assertEqual(learning.validate(self.root),[])

    def test_web_rejects_csrf_rebinding_and_arbitrary_file_access(self):
        self.assertIn("frame-ancestors 'none'",self.csp)
        for kwargs in ({'token':False},{'origin':'https://attacker.example'}):
            with self.assertRaises(HTTPError) as raised:self.post('request',{'topic':'Test'},**kwargs)
            self.assertEqual(raised.exception.code,403)
        with self.assertRaises(HTTPError) as raised:
            urlopen(Request(self.base+'/health',headers={'Host':'attacker.example'}))
        self.assertEqual(raised.exception.code,403)
        for path in ('/data/profile.json','/../../data/profile.json','/api/training'):
            with self.assertRaises(HTTPError):urlopen(self.base+path)
        self.assertEqual(learning.list_records(self.root),[])
        with self.assertRaises(HTTPError):self.post('request',{'topic':{'not':'text'}})
        self.assertEqual(learning.list_records(self.root),[])

    def test_launcher_reuses_only_same_workspace(self):
        result=training_web.run(self.root,self.server.server_port,open_browser=False)
        self.assertEqual(result['url'],self.base+'/')
        other=self.root/'other';workspace.initialize(other)
        with self.assertRaises(ValueError):training_web.run(other,self.server.server_port,open_browser=False)


if __name__=='__main__':unittest.main()
