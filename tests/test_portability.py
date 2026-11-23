"""First-run, cross-workspace and release trust-boundary acceptance tests."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile

from careerflow import core, learning, workspace
from careerflow.__main__ import execute, parser

ROOT=Path(__file__).resolve().parents[1]


def load_script(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/(name+'.py'))
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PortabilityTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base=Path(temporary.name)
        self.root=self.base/'private'

    def command(self,*args):
        options=parser().parse_args(['--root',str(self.root),*args])
        with core.locked(self.root):return execute(options)

    def job(self):
        return core.import_jobs(self.root,[{'employer':'Example','title':'Coordinator',
            'requisition':'R001','url':'https://example.com/job'}])[0]['id']

    def test_blank_onboarding_and_first_draft_without_another_application(self):
        self.command('init')
        profile=core.read(self.root/'data/profile.json')
        self.assertEqual(profile['claims'],{})
        self.assertEqual(profile['employment'],{})
        self.assertEqual(profile['candidate']['name'],'')
        self.assertEqual(self.command('validate')['result'],'valid')
        job=self.job()
        core.screen(self.root,job,'pursue','normal',[
            {'key':k,'status':'pass','detail':'Fictional fixture'} for k in core.REQUIRED_CHECKS],'Fixture')
        core.shortlist(self.root,job)
        self.command('draft',job)
        path=self.root/'applications'/job/'content.json'
        before=path.read_bytes()
        self.assertEqual(core.read(path)['resume']['experience'],[])
        with self.assertRaises(ValueError):self.command('draft',job)
        self.assertEqual(path.read_bytes(),before)
        with self.assertRaisesRegex(ValueError,'candidate name'):core.snapshot(self.root,job)

    def test_initialization_validates_all_inputs_before_writing(self):
        profile=json.loads((ROOT/'examples/fictional-profile.json').read_text())
        profile['claims']['claim-demo']['employment_id']='missing'
        path=self.base/'invalid.json'
        core.write(path,profile)
        with self.assertRaises(ValueError):self.command('init','--profile',str(path))
        self.assertFalse((self.root/'data/profile.json').exists())
        self.assertFalse((self.root/'templates/resume.json').exists())
        profile['claims']['claim-demo']['employment_id']='example-studio'
        profile['claims']['claim-demo']['sources']=[{'kind':'fixture','path':'../../outside.md'}]
        core.write(path,profile)
        with self.assertRaises(ValueError):self.command('init','--profile',str(path))
        self.assertFalse((self.root/'data/profile.json').exists())
        core.write(self.root/'templates/resume.json',{'version':1})
        with self.assertRaises(ValueError):self.command('init')
        self.assertFalse((self.root/'data/profile.json').exists())

    def test_init_preserves_existing_ignore_and_refuses_existing_workspace(self):
        self.root.mkdir()
        (self.root/'.gitignore').write_text('original-rule\n')
        self.command('init')
        self.assertTrue((self.root/'.gitignore').read_text().startswith('original-rule\n'))
        before=(self.root/'data/profile.json').read_bytes()
        with self.assertRaises(ValueError):self.command('init')
        self.assertEqual(before,(self.root/'data/profile.json').read_bytes())
        subprocess.run(['git','init','-q',str(self.root)],check=True)
        for path in ('data/profile.json','training/private.json','interviews/private.md'):
            result=subprocess.run(['git','-C',str(self.root),'check-ignore',path],capture_output=True)
            self.assertEqual(result.returncode,0,path)

    def test_interviews_do_not_invent_submission_or_change_pipeline(self):
        self.command('init');job=self.job()
        notes=self.root/'interviews/debrief.md'
        notes.parent.mkdir();notes.write_text('Reported question; answer and feedback.')
        record=learning.add_interview(self.root,job,'2026-12-01T14:00:00-08:00','Candidate report',Path('interviews/debrief.md'))
        learning.update(self.root,record['id'],'interview','completed','Candidate reported completed')
        current=core.get(self.root,job)
        self.assertEqual(current['stage'],'intake')
        self.assertEqual(current['submissions'],[])
        self.assertEqual(learning.list_records(self.root,'interview')[0]['status'],'completed')
        self.assertEqual(learning.validate(self.root),[])
        count=len(learning.list_records(self.root))
        with self.assertRaises(ValueError):learning.add_interview(self.root,job,'2026-12-01T14:00:00','Report')
        with self.assertRaises(ValueError):learning.add_interview(self.root,'missing','2026-12-01T14:00:00+00:00','Report')
        self.assertEqual(len(learning.list_records(self.root)),count)

    def test_training_completion_needs_evidence_and_never_changes_claims(self):
        self.command('init')
        before=(self.root/'data/profile.json').read_bytes()
        record=learning.add_training(self.root,'Communication','Present a concise project narrative','Agreed exercise')
        original=(self.root/'training'/(record['id']+'.json')).read_bytes()
        with self.assertRaises(ValueError):learning.update(self.root,record['id'],'training','completed','Attempted without artifact')
        self.assertEqual((self.root/'training'/(record['id']+'.json')).read_bytes(),original)
        artifact=self.root/'training/attempt.md';artifact.write_text('Practice artifact and reviewed feedback')
        updated=learning.update(self.root,record['id'],'training','completed','Meets agreed criterion',evidence=Path('training/attempt.md'))
        self.assertEqual(updated['evidence_path'],'training/attempt.md')
        self.assertEqual(len(updated['history']),2)
        self.assertEqual((self.root/'data/profile.json').read_bytes(),before)
        artifact.unlink()
        self.assertTrue(learning.validate(self.root))
        with self.assertRaises(ValueError):learning.update(self.root,record['id'],'training','completed','Cannot reuse missing evidence')

    def test_learning_references_cannot_escape_workspace_even_through_symlink(self):
        self.command('init');job=self.job()
        outside=self.base/'outside.md';outside.write_text('Outside root')
        (self.root/'escape.md').symlink_to(outside)
        for path in (Path('../outside.md'),outside,Path('escape.md')):
            with self.assertRaises(ValueError):learning.add_interview(self.root,job,'2026-12-01T14:00:00+00:00','Report',path)
        self.assertEqual(learning.list_records(self.root),[])
        with self.assertRaises(ValueError):learning.list_records(self.root,limit=-1)

    def test_bundle_excludes_unlisted_files_and_installs_into_both_host_layouts(self):
        pack=load_script('package_skill');installer=load_script('install_skill')
        # Put a fake secret beside the allowlisted inputs in an isolated copy.
        import shutil
        public=self.base/'source'
        for source in pack.members().values():
            target=public/source.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,target)
        (public/'careerflow/private.env').write_text('PRIVATE_SENTINEL')
        (public/'skills/job-application-workflow/references/secret.md').write_text('PRIVATE_SENTINEL')
        bundle=pack.build(self.base/'skill.zip',public)
        with ZipFile(bundle) as archive:
            self.assertFalse(any(b'PRIVATE_SENTINEL' in archive.read(name) for name in archive.namelist()))
        for host in ('.agents','.claude'):
            destination=self.base/host/'skills/job-application-workflow'
            installer.install(bundle,destination)
            target=self.base/(host+'-workspace')
            env={k:v for k,v in os.environ.items() if k!='PYTHONPATH'}
            entry=destination/'scripts/manage_applications.py'
            result=subprocess.run([sys.executable,str(entry),'--root',str(target),'init'],cwd=self.base,env=env,text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertTrue((target/'data/profile.json').exists())
            self.assertFalse((destination/'data').exists())
            before=(destination/'SKILL.md').read_bytes()
            with self.assertRaises(ValueError):installer.install(bundle,destination)
            self.assertEqual((destination/'SKILL.md').read_bytes(),before)

    def test_bundle_installer_rejects_tampering_and_path_escape_before_writing(self):
        pack=load_script('package_skill');installer=load_script('install_skill')
        good=pack.build(self.base/'good.zip')
        for malicious in ('tamper','escape'):
            bad=self.base/(malicious+'.zip')
            with ZipFile(good) as original,ZipFile(bad,'w') as output:
                for name in original.namelist():
                    content=original.read(name)
                    if malicious=='tamper' and name.endswith('/SKILL.md'):content+=b'changed'
                    output.writestr(name,content)
                if malicious=='escape':output.writestr('../escaped.txt','bad')
            target=self.base/malicious/'job-application-workflow'
            with self.assertRaises(ValueError):installer.install(bad,target)
            self.assertFalse(target.exists())
        self.assertFalse((self.base/'escaped.txt').exists())

    def test_cli_default_workspace_is_current_directory_not_installation(self):
        env={k:v for k,v in os.environ.items() if k!='PYTHONPATH'}
        wrapper=ROOT/'skills/job-application-workflow/scripts/manage_applications.py'
        result=subprocess.run([sys.executable,str(wrapper),'init'],cwd=self.base,env=env,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertTrue((self.base/'data/profile.json').exists())

    def test_source_distribution_has_no_personal_data_paths(self):
        # The standalone release inventory is fixed, not a recursive workspace copy.
        pack=load_script('package_skill')
        names=pack.members()
        self.assertTrue(all(name.startswith('job-application-workflow/') for name in names))
        for name in names:
            self.assertFalse(any(part in {'data','applications','.git','.playwright-mcp','employment','profile'} for part in Path(name).parts),name)


if __name__=='__main__':unittest.main()
