"""Loopback-only training UI. Uses the same locked records as the CLI."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.parse import urlsplit, parse_qs
from urllib.request import urlopen
import webbrowser

from . import core, learning, training


def make_server(root, port=8872):
    root=root.resolve()
    token=secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass

        def send(self,status,body,content_type='application/json'):
            if content_type=='application/json':body=json.dumps(body,ensure_ascii=False)
            encoded=body.encode()
            self.send_response(status)
            self.send_header('Content-Type',content_type+'; charset=utf-8')
            self.send_header('Content-Length',str(len(encoded)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'none'; script-src 'nonce-"+token+"'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers();self.wfile.write(encoded)

        def allowed_host(self):
            return self.headers.get('Host') in {f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}

        def do_GET(self):
            if not self.allowed_host():return self.send(403,{'error':'Local host required'})
            target=urlsplit(self.path)
            try:
                if target.path=='/health':return self.send(200,{'app':'careerflow-training','workspace':str(root)})
                if target.path=='/':
                    html=(Path(__file__).parent/'assets/training.html').read_text().replace('__TOKEN__',token)
                    return self.send(200,html,'text/html')
                if target.path!='/api/training':return self.send(404,{'error':'Not found'})
                if self.headers.get('X-Careerflow-Token')!=token:return self.send(403,{'error':'Session token required'})
                with core.locked(root):
                    record_id=parse_qs(target.query).get('id',[None])[0]
                    if record_id:return self.send(200,training.get(root,record_id))
                    records=learning.list_records(root,'training',limit=1000)
                    return self.send(200,{'workspace':str(root),'records':[
                        {k:r.get(k) for k in ('id','topic','goal','status','updated_at')} |
                        {'phase':r.get('session',{}).get('phase','legacy')} for r in records]})
            except (ValueError,KeyError,OSError) as exc:self.send(400,{'error':str(exc)})

        def do_POST(self):
            origin=self.headers.get('Origin')
            allowed_origins={f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'}
            if (not self.allowed_host() or self.headers.get('X-Careerflow-Token')!=token
                    or (origin is not None and origin not in allowed_origins)
                    or self.headers.get('Content-Type')!='application/json'):
                return self.send(403,{'error':'Same-origin JSON request with session token required'})
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=1_100_000:return self.send(413,{'error':'Request exceeds size limit or is empty'})
                data=json.loads(self.rfile.read(length))
                if not isinstance(data,dict):raise ValueError('Expected JSON object')
                with core.locked(root):
                    if self.path=='/api/request':
                        record=training.request(root,data.get('topic',''),data.get('minutes',30),data.get('focus',''),data.get('job') or None)
                    elif self.path=='/api/start':record=training.start(root,data['id'])
                    elif self.path=='/api/draft':record=training.save_draft(root,data['id'],data.get('text',''))
                    elif self.path=='/api/attempt':record=training.attempt(root,data['id'],data.get('text',''),data.get('note','Submitted from training web app'))
                    elif self.path=='/api/complete':record=training.complete(root,data['id'],'Candidate completed the reviewed exercise from the training web app')
                    else:return self.send(404,{'error':'Not found'})
                self.send(200,record)
            except (ValueError,KeyError,OSError,TypeError) as exc:self.send(400,{'error':str(exc)})

    return ThreadingHTTPServer(('127.0.0.1',port),Handler)


def health(port):
    try:
        with urlopen(f'http://127.0.0.1:{port}/health',timeout=0.5) as response:
            result=json.loads(response.read(4096))
            return result if isinstance(result,dict) else {'app':'other'}
    except (URLError,OSError,ValueError):return None


def run(root, port=8872, foreground=False, open_browser=True):
    root=root.resolve()
    if not (root/'data/profile.json').is_file():
        raise ValueError('Initialize this private workspace first with careerflow --root PATH init')
    if not 1<=port<=65535:raise ValueError('Port must be 1–65535')
    url=f'http://127.0.0.1:{port}/'
    if foreground:
        with make_server(root,port) as server:
            print('Training sessions: '+url,flush=True)
            server.serve_forever()
        return {'url':url}
    running=health(port)
    if running:
        if running.get('app')!='careerflow-training' or running.get('workspace')!=str(root):
            raise ValueError('Port belongs to another app/workspace; choose another --port')
    else:
        directory=root/'.careerflow';directory.mkdir(parents=True,exist_ok=True)
        log=directory/'training-web.log'
        env=os.environ.copy()
        env['PYTHONPATH']=str(Path(__file__).resolve().parent.parent)+os.pathsep+env.get('PYTHONPATH','')
        with log.open('a') as output:
            child=subprocess.Popen([sys.executable,'-m','careerflow','--root',str(root),'training-web','--port',str(port),'--foreground','--no-browser'],
                stdin=subprocess.DEVNULL,stdout=output,stderr=output,start_new_session=True,env=env,
                cwd=Path(__file__).resolve().parent.parent)
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            running=health(port)
            if running and running.get('app')=='careerflow-training' and running.get('workspace')==str(root):break
            if child.poll() is not None:raise ValueError('Web server could not start; inspect '+str(log))
            time.sleep(0.1)
        else:
            child.terminate()
            raise ValueError('Web server did not become ready; inspect '+str(log))
        core.write(directory/'training-web.json',{'pid':child.pid,'port':port,'url':url})
    if open_browser:webbrowser.open(url)
    return {'url':url,'workspace':str(root),'result':'Training web app ready; agent generation is requested through the skill'}
