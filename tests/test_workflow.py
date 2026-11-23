import copy
import json
from pathlib import Path
import tempfile
import subprocess
import time
import unittest

from careerflow import core, render, dashboard


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        (self.root/'evidence.md').write_text('Synthetic fixture evidence; not candidate data.')
        self.profile={'schema_version':1,'revision':1,'candidate':{'name':'Test Candidate','email':'test@example.com','phone':'555-0100','linkedin':'https://example.com/test'},
            'employment':{'example':{'employer':'Example Systems','title':'Engineer','dates':'2020–Present'}},
            'education':['B.S. Engineering — Example University'], 'preferences':{},'claims':{}}
        for cid,text in [('claim-one','Developed a device driver.'),('claim-two','Investigated device initialization failures.'),('claim-unused','Mentored engineers.')]:
            self.profile['claims'][cid]={'id':cid,'employment_id':'example','text':text,'revision':1,'status':'active','verification':'fixture',
                'sources':[{'kind':'fixture','path':'evidence.md'}],'tags':['driver'],'history':[]}
        core.write(self.root/'data/profile.json',self.profile)
        core.write(self.root/'templates/resume.json',core.read(Path(core.__file__).parent/'assets/resume.json'))

    def test_lock_initializes_new_workspace(self):
        fresh=self.root/'new-workspace'
        with core.locked(fresh):
            self.assertEqual(core.records(fresh),[])
        self.assertTrue((fresh/'.careerflow/write.lock').exists())

    def job(self, req='R001'):
        return {'employer':'Example Co','title':'Engineer','url':'https://jobs.example/role_'+req+'?q=ignored','requisition':req}

    def prepare(self):
        app_id=core.import_jobs(self.root,[self.job()])[0]['id']
        core.screen(self.root,app_id,'pursue','normal',[{'key':key,'status':'pass','detail':'Synthetic fixture evidence'} for key in sorted(core.REQUIRED_CHECKS)],'Fixture')
        core.shortlist(self.root,app_id)
        core.write(self.root/'applications'/app_id/'content.json',{'schema_version':1,'resume':{'headline':'Embedded Engineer','summary':'Engineer with driver experience.','skills':['C and debugging'],
            'experience':[{'employment_id':'example','claim_ids':['claim-one','claim-two']}]},'letter':['Dear Hiring Team,','I am applying for the role.','Test Candidate'],
            'letter_claim_ids':['claim-two'],'build_options':{'layouts':['plain'],'include_letter':True}})
        return app_id

    def test_application_contact_email_is_scoped_and_validated(self):
        app_id = self.prepare()
        path = self.root/'applications'/app_id/'content.json'
        original = core.snapshot(self.root, app_id)
        content = core.read(path)
        content.update(contact_email='portal@example.com', contact_email_source='Candidate confirmation')
        core.write(path, content)
        changed = core.snapshot(self.root, app_id)
        self.assertEqual(changed['candidate']['email'], 'portal@example.com')
        self.assertEqual(core.read(self.root/'data/profile.json')['candidate']['email'], 'test@example.com')
        self.assertNotEqual(core.digest(original), core.digest(changed))
        for email, source in [('bad address', 'confirmed'), ('portal@example.com', '')]:
            content.update(contact_email=email, contact_email_source=source)
            core.write(path, content)
            with self.assertRaises(ValueError):
                core.snapshot(self.root, app_id)

    def test_employment_title_override_is_scoped_and_requires_provenance(self):
        app_id = self.prepare()
        path = self.root/'applications'/app_id/'content.json'
        original = core.snapshot(self.root, app_id)
        content = core.read(path)
        content['employment_title_overrides'] = {'example': {
            'title': 'L5 Engineer', 'source': 'Candidate confirmed internal display title'}}
        core.write(path, content)
        changed = core.snapshot(self.root, app_id)
        self.assertEqual(changed['employment']['example']['title'], 'L5 Engineer')
        self.assertIn('L5 Engineer', render.resume_markdown(changed))
        self.assertEqual(core.read(self.root/'data/profile.json')['employment']['example']['title'], 'Engineer')
        self.assertNotEqual(core.digest(original), core.digest(changed))
        for override in [{}, {'title': 'L5 Engineer', 'source': ''}]:
            content['employment_title_overrides'] = {'example': override}
            core.write(path, content)
            with self.assertRaises(ValueError):
                core.snapshot(self.root, app_id)
        content['employment_title_overrides'] = {'unknown': {'title': 'Engineer', 'source': 'Confirmed'}}
        core.write(path, content)
        with self.assertRaises(ValueError):
            core.snapshot(self.root, app_id)

    def test_deduplicates_workday_style_urls(self):
        first=self.job();second=self.job();second['url']='https://jobs.example/different_slug_R001-1?utm_source=test'
        result=core.import_jobs(self.root,[first,second])
        self.assertEqual([r['result'] for r in result],['created','duplicate'])
        self.assertFalse((self.root/'applications').exists())

    def test_one_page_styled_resume_includes_education_without_optional_contacts(self):
        app_id=self.prepare()
        core.profile_set(self.root,'linkedin','','Candidate omitted optional link')
        core.profile_set(self.root,'phone','','Candidate omitted optional phone')
        built=render.build(self.root,app_id,('styled',),False)
        pdf=self.root/built['path']/'resume-styled.pdf'
        text=subprocess.check_output(['pdftotext',str(pdf),'-'],text=True)
        self.assertIn('Example University',' '.join(text.split()))
        self.assertNotIn('LinkedIn profile',text)
        self.assertEqual(core.read(pdf.parent/'manifest.json')['outputs'][pdf.name]['pages'],1)

    def test_invalid_batch_is_not_partially_imported(self):
        with self.assertRaises(ValueError):core.import_jobs(self.root,[self.job(),{'employer':'Example','url':'file:///tmp/no','title':'Bad'}])
        self.assertEqual(core.records(self.root),[])

    def test_screening_blocks_unknown_failed_and_declined(self):
        app_id=core.import_jobs(self.root,[self.job()])[0]['id']
        with self.assertRaises(ValueError):core.shortlist(self.root,app_id)
        core.screen(self.root,app_id,'pursue','normal',[{'key':'location','status':'review','detail':'Unresolved'}],'Fixture')
        with self.assertRaises(ValueError):core.shortlist(self.root,app_id)
        core.shortlist(self.root,app_id,'Build a review draft despite unknown location; no submission')
        core.screen(self.root,app_id,'pursue','normal',[{'key':'eligibility','status':'fail','detail':'Known unmet condition'}],'Fixture')
        with self.assertRaises(ValueError):core.shortlist(self.root,app_id,'Do not silently override fail')
        core.screen(self.root,app_id,'decline','normal',[],'User declined')
        with self.assertRaises(ValueError):render.build(self.root,app_id)

    def test_build_cache_and_selected_dependency_invalidation(self):
        app_id=self.prepare();first=render.build(self.root,app_id,('plain',),True)
        self.assertEqual(render.build(self.root,app_id,('plain',),True)['result'],'cached')
        profile=core.read(self.root/'data/profile.json');profile['claims']['claim-unused']['text']='Unrelated new fact.';core.write(self.root/'data/profile.json',profile)
        self.assertEqual(core.current_build(self.root,core.get(self.root,app_id)),'current')
        profile['claims']['claim-one']['text']='Developed and debugged a device driver.';profile['claims']['claim-one']['revision']+=1;core.write(self.root/'data/profile.json',profile)
        self.assertEqual(core.current_build(self.root,core.get(self.root,app_id)),'stale')
        second=render.build(self.root,app_id,('plain',),True)
        self.assertNotEqual(first['id'],second['id'])
        self.assertTrue((self.root/first['path']/'input.json').exists())

    def test_intake_supersession_history_and_retry(self):
        self.prepare()
        note=core.add_note(self.root,'Developed and debugged a driver.','example','User statement','Device project')
        result=core.accept_note(self.root,note['id'],None,'claim-one',['driver'])
        self.assertEqual(result['revision'],2)
        self.assertEqual(core.accept_note(self.root,note['id'],None,'claim-one')['result'],'already_accepted')
        profile=core.read(self.root/'data/profile.json')
        self.assertEqual(profile['claims']['claim-one']['history'][0]['text'],'Developed a device driver.')
        self.assertEqual(len(core.impact(self.root,'claim-one')),1)

    def test_employment_and_preference_updates(self):
        core.employment_set(self.root,'new-employer',{'employer':'New Employer','title':'Engineer','dates':'2010–2012'},'User')
        core.preference_set(self.root,'remote',True,'User')
        note=core.add_note(self.root,'Additional project work.','new-employer','User')
        result=core.accept_note(self.root,note['id'],None)
        self.assertIn(result['claim_id'],core.read(self.root/'data/profile.json')['claims'])

    def test_submission_review_gate_and_frozen_snapshot(self):
        app_id=self.prepare();build=render.build(self.root,app_id,('plain',),True)
        with self.assertRaises(ValueError):render.record_submission(self.root,app_id,'2026-11-03','Fixture submission')
        render.review(self.root,app_id,True,True,'Synthetic test fixture review only')
        submitted=render.record_submission(self.root,app_id,'2026-11-03','User-reported fixture submission')
        frozen=self.root/submitted['path']/'input.json';before=frozen.read_bytes()
        core.profile_set(self.root,'email','new@example.com','User')
        self.assertEqual(frozen.read_bytes(),before)
        self.assertEqual(core.get(self.root,app_id)['stage'],'applied')
        with self.assertRaises(ValueError):render.build(self.root,app_id)

    def test_tampered_artifact_cannot_be_recorded_as_submitted(self):
        app_id=self.prepare();b=render.build(self.root,app_id,('plain',),True)
        render.review(self.root,app_id,True,True,'Synthetic test review')
        (self.root/b['path']/'resume-plain.pdf').write_bytes(b'changed')
        with self.assertRaises(ValueError):render.record_submission(self.root,app_id,'2026-11-03','Fixture')

    def test_readable_snapshot_restores_full_state(self):
        self.prepare();snapshot=core.checkpoint(self.root)
        before=core.records(self.root)
        with tempfile.TemporaryDirectory() as other:
            target=Path(other);core.restore(target,self.root/snapshot['snapshot'])
            self.assertEqual(core.records(target),before)
            with self.assertRaises(ValueError):core.restore(target,self.root/snapshot['snapshot'])

    def test_1000_jobs_stay_in_database_without_directories(self):
        start=time.perf_counter()
        jobs=[self.job('R'+str(n)) for n in range(1000)]
        result=core.import_jobs(self.root,jobs)
        self.assertEqual(len(result),1000)
        self.assertFalse((self.root/'applications').exists())
        self.assertEqual(len(core.search(self.root,limit=2000)),1000)
        self.assertEqual(len(core.search(self.root,query='R999')),1)
        dashboard.make(self.root)
        self.assertFalse((self.root/'applications').exists())
        self.assertIn('1000 jobs tracked',(self.root/'APPLICATIONS.md').read_text())
        self.assertLess((self.root/'APPLICATIONS.md').stat().st_size,30000)
        print('\nSynthetic 1,000-job import/search/dashboard: %.3fs'%(time.perf_counter()-start))

    def test_batch_screening_is_atomic(self):
        app_id=core.import_jobs(self.root,[self.job()])[0]['id']
        with self.assertRaises(ValueError):core.screen_batch(self.root,[{'id':app_id,'pursuit':'pursue','checks':[],'reason':'Fixture'},{'id':'missing','pursuit':'decline','checks':[],'reason':'Fixture'}])
        self.assertEqual(core.get(self.root,app_id)['stage'],'intake')

    def test_posting_snapshots_deduplicate_and_restore(self):
        app_id=core.import_jobs(self.root,[self.job()])[0]['id']
        result=core.source_snapshot(self.root,app_id,'Synthetic job description.','https://jobs.example/role_R001','provided')
        self.assertEqual(core.source_snapshot(self.root,app_id,'Synthetic job description.','https://jobs.example/role_R001','provided')['result'],'already_saved')
        self.assertFalse((self.root/'applications').exists())
        core.checkpoint(self.root)
        with tempfile.TemporaryDirectory() as other:
            root=Path(other);core.restore(root,self.root/'data/jobs.jsonl')
            db=core.database(root)
            self.assertEqual(db.execute('SELECT body FROM posting_snapshots WHERE sha256=?',(result['snapshot_id'],)).fetchone()[0],'Synthetic job description.')
            db.close()

    def test_path_escape_is_rejected(self):
        with self.assertRaises(ValueError):core.local(self.root,'../outside')


if __name__=='__main__':unittest.main()
