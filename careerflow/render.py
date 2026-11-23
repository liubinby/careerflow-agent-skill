"""Shared renderer: no employer names, contact strings, or fixed page counts."""
from pathlib import Path
from xml.sax.saxutils import escape
import json
import re
import shutil
import subprocess
import tempfile

from . import core


def markup(text):
    text = escape(text)
    text = re.sub(r'\[([^\]]+)\]\((https?://[^)]+)\)', r'<a href="\2" color="black">\1</a>', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    return re.sub(r'`([^`]+)`', r'\1', text)


def resume_markdown(s):
    c, r = s['candidate'], s['content']['resume']
    lines = ['# ' + c['name'], '', ' | '.join(x for x in (c['email'],c['phone']) if x), '']
    if c['linkedin']:lines += ['[LinkedIn](' + c['linkedin'] + ')','']
    lines += ['## ' + r['headline'], '', r['summary'], '', '## Skills', '']
    lines.extend('- ' + x for x in r['skills'])
    lines.extend(['', '## Professional Experience', ''])
    for selection in r['experience']:
        e = s['employment'][selection['employment_id']]
        lines.extend(['### ' + e['employer'] + ' — ' + e['title'], e['dates'], ''])
        lines.extend('- ' + s['claims'][cid]['text'] for cid in selection['claim_ids'])
        lines.append('')
    lines.extend(['## Education', ''])
    lines.extend(s['education'])
    return '\n'.join(lines) + '\n'


def pdf(s, output, layout):
    from reportlab.lib.colors import HexColor
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import (BaseDocTemplate, SimpleDocTemplate, Frame, PageTemplate,
                                    Paragraph, KeepTogether, Spacer)
    t, c, r = s['template'], s['candidate'], s['content']['resume']
    body = ParagraphStyle('body', fontName=t['font'], fontSize=t['body_size'], leading=t['leading'], spaceAfter=6)
    heading = ParagraphStyle('heading', parent=body, fontName='Helvetica-Bold', fontSize=12, leading=15, spaceBefore=9, spaceAfter=6, keepWithNext=True)
    title = ParagraphStyle('title', parent=body, fontName='Helvetica-Bold', fontSize=22, leading=26, spaceAfter=8)
    small = ParagraphStyle('small', parent=body, fontSize=9.3, leading=12.7, spaceAfter=10)
    bullet = ParagraphStyle('bullet', parent=body, leftIndent=9, firstLineIndent=-9)
    p = lambda text, style=body: Paragraph(markup(text), style)
    jobs = []
    for selection in r['experience']:
        e = s['employment'][selection['employment_id']]
        block = [p(e['employer'], heading), p(e['title'] + ' | ' + e['dates'], small)]
        block.extend(p('• ' + s['claims'][cid]['text'], bullet) for cid in selection['claim_ids'])
        jobs.append(KeepTogether(block))
    page = (612, 792)
    if layout == 'plain':
        story = [p(c['name'], title), p(' | '.join(x for x in (c['email'],c['phone']) if x))]
        if c['linkedin']:story.append(p('[LinkedIn](' + c['linkedin'] + ')'))
        story += [p(r['headline'], heading), p(r['summary']), p('Skills', heading)]
        story.extend(p('• ' + x, bullet) for x in r['skills'])
        story.append(p('Professional Experience', heading))
        story.extend(jobs)
        story.append(p('Education', heading))
        story.extend(p(x) for x in s['education'])
        SimpleDocTemplate(str(output), pagesize=page, leftMargin=48, rightMargin=48,
                          topMargin=40, bottomMargin=40, author=c['name'], title=c['name'] + ' Resume').build(story)
        return
    if layout != 'styled':
        raise ValueError('Unknown layout')
    summary = p(r['summary'])
    _, sh = summary.wrap(528, 1000)
    top = 649 - sh - 40
    if top < 400:
        raise ValueError('Summary is too long for styled layout; shorten it or use plain')
    doc = BaseDocTemplate(str(output), pagesize=page, author=c['name'], title=c['name'] + ' Resume')

    def background(canvas, document):
        number = document.page
        canvas.saveState()
        canvas.setFillColor(HexColor(t['background'])); canvas.rect(0, 0, 612, 792, fill=1, stroke=0)
        canvas.setFillColor(HexColor(t['accent']))
        nominal = 40 if number == 1 else 25
        name_size = min(nominal, nominal*t['main_width']/max(canvas.stringWidth(c['name'],'Helvetica-Bold',nominal),1))
        if name_size < 14:raise ValueError('Name too long for styled header; use plain layout')
        canvas.setFont('Helvetica-Bold',name_size)
        canvas.drawString(t['main_left'], 717 if number == 1 else 737, c['name'])
        canvas.setFillColor(HexColor(t['ink'])); canvas.setFont(t['font'], 9.5)
        contact_y = 749
        contact = [c['email'],c['phone']]
        if c['linkedin']:contact.append('[LinkedIn profile]('+c['linkedin']+')')
        for text in filter(None,contact):
            item=p(text,small);_,h=item.wrap(t['sidebar_width'],1000)
            if contact_y-h < 658:raise ValueError('Contact block too tall for styled header; use plain layout')
            item.drawOn(canvas,t['left'],contact_y-h);contact_y-=h+3
        hp = p(r['headline'].upper(), small)
        _, hh = hp.wrap(t['main_width'], 1000)
        hp.drawOn(canvas, t['main_left'], (698 if number == 1 else 721)-hh)
        if number == 1:
            summary.drawOn(canvas, 42, 649-sh)
        line_y = top + 20 if number == 1 else 682
        canvas.setStrokeColor(HexColor(t['accent'])); canvas.setLineWidth(1.5); canvas.line(42,line_y,570,line_y)
        sy = top if number == 1 else 655
        items = []
        if number == 1:
            items += [p('SKILLS',heading)] + [p(x,small) for x in r['skills']]
            if s['education']:items += [p('EDUCATION',heading)] + [p(x,small) for x in s['education']]
        for item in items:
            _, h = item.wrap(t['sidebar_width'], 1000)
            if sy-h < 45:
                raise ValueError('Sidebar overflow; reduce selected skills or use plain layout')
            item.drawOn(canvas,42,sy-h); sy -= h + 10
        canvas.setFillColor(HexColor(t['accent'])); canvas.setFont(t['font'],8)
        canvas.drawString(42,23,c['name'] + ' | ' + s['application']['employer'] + ' ' + s['application']['requisition'])
        canvas.drawRightString(570,23,str(number))
        canvas.restoreState()
        if number == 1:
            document.handle_nextPageTemplate('later')

    first = Frame(t['main_left'], 42, t['main_width'], top-42, leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)
    later = Frame(t['main_left'], 42, t['main_width'], 613, leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id='first', frames=[first], onPage=background),
                          PageTemplate(id='later', frames=[later], onPage=background)])
    doc.build([p('EXPERIENCE',heading)] + jobs)


def letter_pdf(s, output):
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph
    c = s['candidate']
    style = ParagraphStyle('letter', fontName='Helvetica',fontSize=11,leading=15,spaceAfter=10)
    title = ParagraphStyle('title',parent=style,fontName='Helvetica-Bold',fontSize=22,leading=26)
    story = [Paragraph(escape(c['name']),title), Paragraph(escape(c['email']+' | '+c['phone']),style)]
    story.extend(Paragraph(markup(x),style) for x in s['content']['letter'])
    SimpleDocTemplate(str(output),pagesize=(612,792),leftMargin=50,rightMargin=50,
                      topMargin=44,bottomMargin=44,author=c['name'],title=c['name']+' Cover Letter').build(story)


def build(root, app_id, layouts=('styled',), include_letter=False):
    r = core.get(root, app_id)
    if r['pursuit'] != 'pursue' or r['stage'] not in {'shortlisted','prepared'}:
        raise ValueError('Build only shortlisted/prepared jobs with pursuit=pursue')
    if any(c['status']=='fail' for c in r['checks']):
        raise ValueError('Failed screening condition blocks build')
    if core.needs_review(r) and not r.get('shortlist_override'):
        raise ValueError('Resolve screening or record a shortlist override before building')
    s = core.snapshot(root,app_id)
    # Persist explicit build options in content so freshness includes the chosen output set.
    desired = {'layouts':list(layouts),'include_letter':include_letter}
    if s['content'].get('build_options') != desired:
        content_path = root/'applications'/app_id/'content.json'
        content = core.read(content_path); content['build_options']=desired; core.write(content_path,content)
        s=core.snapshot(root,app_id)
    build_id=core.digest(s)[:20]
    parent=root/'applications'/app_id/'builds'; parent.mkdir(exist_ok=True)
    destination=parent/build_id
    if destination.exists():
        if core.read(destination/'manifest.json')['fingerprint'] != core.digest(s):
            raise ValueError('Build hash collision')
        r['latest_build']=build_id; core.save(root,r)
        return {'id':build_id,'result':'cached','path':str(destination.relative_to(root))}
    staging=Path(tempfile.mkdtemp(prefix='.building-',dir=parent))
    try:
        core.write(staging/'input.json',s)
        (staging/'resume.md').write_text(resume_markdown(s))
        for layout in layouts:
            pdf(s,staging/('resume-'+layout+'.pdf'),layout)
        if include_letter:
            if not s['content'].get('letter'):
                raise ValueError('No cover letter content')
            letter_pdf(s,staging/'cover-letter.pdf')
        outputs={}
        for path in staging.glob('*.pdf'):
            text=subprocess.check_output(['pdftotext',str(path),'-'],text=True)
            normalized=' '.join(text.split())
            for value in [s['candidate']['name'],s['candidate']['email'],s['candidate']['phone']]:
                if value and value not in normalized:
                    raise ValueError('Missing PDF contact text: '+value)
            info=subprocess.check_output(['pdfinfo',str(path)],text=True)
            pages=int(re.search(r'^Pages:\s+(\d+)',info,re.M).group(1))
            outputs[path.name]={'sha256':core.hashlib.sha256(path.read_bytes()).hexdigest(),'pages':pages}
        manifest={'schema_version':1,'fingerprint':core.digest(s),'created_at':core.now(),
                  'outputs':outputs,'qa':{'text_checked':True,'visual_checked':False,'candidate_reviewed':False},
                  'review_history':[]}
        core.write(staging/'manifest.json',manifest)
        staging.rename(destination)
    except Exception:
        shutil.rmtree(staging,ignore_errors=True)
        raise
    r['latest_build']=build_id; r['stage']='prepared'
    core.event(r,'build',build_id); core.save(root,r)
    return {'id':build_id,'result':'built','path':str(destination.relative_to(root)),'qa':manifest['qa']}


def review(root, app_id, visual, candidate, note):
    r=core.get(root,app_id)
    if not note.strip() or not r.get('latest_build') or core.current_build(root,r)!='current':
        raise ValueError('Review requires a current build and an evidence note')
    path=root/'applications'/app_id/'builds'/r['latest_build']/'manifest.json'
    m=core.read(path)
    m['qa']['visual_checked'] |= visual; m['qa']['candidate_reviewed'] |= candidate
    m['review_history'].append({'at':core.now(),'visual':visual,'candidate':candidate,'note':note})
    core.write(path,m)
    return m['qa']


def record_submission(root, app_id, date, confirmation):
    from datetime import date as Date
    Date.fromisoformat(date)
    r=core.get(root,app_id)
    if not confirmation.strip() or r['pursuit']!='pursue' or r['stage']!='prepared' or core.current_build(root,r)!='current':
        raise ValueError('Submission record requires a current prepared build, pursuit=pursue, and confirmation')
    source=root/'applications'/app_id/'builds'/r['latest_build']
    m=core.read(source/'manifest.json')
    if not all(m['qa'].values()):
        raise ValueError('Text, visual, and candidate review are required')
    for filename, meta in m['outputs'].items():
        if core.hashlib.sha256((source/filename).read_bytes()).hexdigest()!=meta['sha256']:
            raise ValueError('Artifact changed since build')
    target=root/'applications'/app_id/'submissions'/(date+'-'+r['latest_build'])
    if target.exists():
        raise ValueError('Submission already recorded')
    shutil.copytree(source,target)
    record={'submitted_on':date,'confirmation':confirmation,'build_id':r['latest_build'],'path':str(target.relative_to(root))}
    core.write(target/'submission.json',record)
    r['submissions'].append(record);r['stage']='applied'
    core.event(r,'record_manual_submission',record);core.save(root,r)
    return record
