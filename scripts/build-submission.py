#!/usr/bin/env python3
"""Build the combined PDF from the handoff Markdown and verified local assets.
Requires reportlab and pypdf. Run from any directory; output lives under output/pdf.
"""
from pathlib import Path
import html
import json
import re
import textwrap
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer,
    PageBreak, NextPageTemplate, Image, Table, TableStyle, Preformatted, KeepTogether)
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/pdf/DOKS_TAM_Case_Study.pdf'
OUT.parent.mkdir(parents=True,exist_ok=True)
BLUE=colors.HexColor('#0069ff'); NAVY=colors.HexColor('#102c50'); MUTED=colors.HexColor('#52657c')
styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='Body',fontName='Helvetica',fontSize=9.5,leading=13.2,spaceAfter=7,textColor=NAVY))
styles.add(ParagraphStyle(name='TitleMain',fontName='Helvetica-Bold',fontSize=31,leading=37,spaceAfter=18,textColor=NAVY))
styles.add(ParagraphStyle(name='H1x',fontName='Helvetica-Bold',fontSize=22,leading=27,spaceAfter=15,textColor=NAVY,keepWithNext=True))
styles.add(ParagraphStyle(name='H2x',fontName='Helvetica-Bold',fontSize=13,leading=17,spaceBefore=12,spaceAfter=7,textColor=BLUE,keepWithNext=True))
styles.add(ParagraphStyle(name='H3x',fontName='Helvetica-Bold',fontSize=10.5,leading=14,spaceBefore=8,spaceAfter=6,textColor=NAVY,keepWithNext=True))
styles.add(ParagraphStyle(name='Smallx',fontName='Helvetica',fontSize=8.5,leading=11.3,spaceAfter=7,textColor=MUTED))
styles.add(ParagraphStyle(name='Cell',fontName='Helvetica',fontSize=8.5,leading=11.3,textColor=NAVY,spaceAfter=0))
styles.add(ParagraphStyle(name='CellHead',parent=styles['Cell'],fontName='Helvetica-Bold',textColor=colors.white))
styles.add(ParagraphStyle(name='Codex',fontName='Courier',fontSize=7.6,leading=10,backColor=colors.HexColor('#f1f5fa'),borderPadding=8,spaceBefore=3,spaceAfter=9))

def ascii_punctuation(text):
    return text.translate(str.maketrans({'\u2013':'-','\u2014':'-','\u2011':'-','\u2019':"'",'\u2018':"'",'\u201c':'"','\u201d':'"','\u2192':' -> ','\u2265':'>=','\u00b7':' | ','\u00a0':' '}))

def rich(text):
    text=html.escape(ascii_punctuation(text))
    text=re.sub(r'\[([^\]]+)\]\((https?://[^)]+)\)',r'<link href="\2" color="#0069ff">\1</link>',text)
    # Relative file paths remain legible evidence references in the portable PDF.
    text=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',r'\1 (\2)',text)
    text=re.sub(r'\*\*(.*?)\*\*',r'<b>\1</b>',text)
    text=re.sub(r'`([^`]+)`',r'<font name="Courier" size="8">\1</font>',text)
    return text

def p(text,style='Body'): return Paragraph(rich(text),styles[style])

def table(rows,width=504):
    n=len(rows[0]); first=' '.join(rows[0])
    weights={2:[.27,.73],3:[.28,.44,.28],4:[.23,.26,.25,.26]}.get(n,[1/n]*n)
    if 'Light:' in first: weights=[.34,.33,.33]
    if 'Calculation' in first: weights=[.36,.43,.21]
    cells=[[p(c,'CellHead' if i==0 else 'Cell') for c in row] for i,row in enumerate(rows)]
    t=Table(cells,colWidths=[width*w for w in weights],repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),NAVY),('VALIGN',(0,0),(-1,-1),'TOP'),
        ('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),
        ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#f1f5fb'),colors.white]),
        ('LINEBELOW',(0,0),(-1,0),.7,BLUE),('LINEBELOW',(0,1),(-1,-1),.3,colors.HexColor('#d6e0ed'))]))
    return [t,Spacer(1,10)]

def markdown(path):
    lines=path.read_text().splitlines(); story=[]; i=0
    while i<len(lines):
        line=lines[i].strip()
        if not line: i+=1; continue
        if line=='<!-- PAGEBREAK -->': story.append(PageBreak()); i+=1; continue
        if line.startswith('```'):
            i+=1; code=[]
            while i<len(lines) and not lines[i].startswith('```'):
                code.extend(textwrap.wrap(ascii_punctuation(lines[i]),width=100,replace_whitespace=False,drop_whitespace=False) or ['']); i+=1
            story.append(Preformatted('\n'.join(code),styles['Codex'])); i+=1; continue
        if line.startswith('|'):
            rows=[]
            while i<len(lines) and lines[i].strip().startswith('|'):
                row=[x.strip() for x in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r'[:\- ]+',cell) for cell in row): rows.append(row)
                i+=1
            story.extend(table(rows)); continue
        if line.startswith('#'):
            level=len(line)-len(line.lstrip('#')); heading=p(line[level:].strip(),{1:'H1x',2:'H2x'}.get(level,'H3x'))
            if level==1: heading.section_title=line[level:].strip()
            story.append(heading); i+=1; continue
        if line.startswith('- '): story.append(p('- '+line[2:])); i+=1; continue
        paragraph=[line]; i+=1
        while i<len(lines) and lines[i].strip() and not lines[i].startswith(('#','|','```','<!--','- ')):
            paragraph.append(lines[i].strip()); i+=1
        story.append(p(' '.join(paragraph)))
    return story

class Report(BaseDocTemplate):
    def afterFlowable(self,flowable):
        if hasattr(flowable,'section_title'):
            title=flowable.section_title; self.sections[title]=self.page
            key=f'section-{len(self.sections)}'; self.canv.bookmarkPage(key); self.canv.addOutlineEntry(title,key,0)

def decorate(canvas,doc):
    w,h=canvas._pagesize
    canvas.saveState(); canvas.setStrokeColor(BLUE); canvas.setLineWidth(2); canvas.line(42,h-31,w-42,h-31)
    canvas.setFont('Helvetica',8); canvas.setFillColor(MUTED)
    canvas.drawString(42,h-22,'DIGITALOCEAN KUBERNETES  /  TAM CASE STUDY')
    canvas.drawString(42,24,'Pooja Singh  |  October 30, 2026  |  Demo evidence and customer handoff')
    canvas.drawRightString(w-42,24,str(doc.page)); canvas.restoreState()

doc=Report(str(OUT),pagesize=letter,leftMargin=54,rightMargin=54,topMargin=51,bottomMargin=46,
    title='DOKS Scalable Web App - TAM Case Study',author='Pooja Singh')
doc.sections={}
for name,size in [('portrait',letter),('landscape',landscape(letter))]:
    w,h=size
    doc.addPageTemplates(PageTemplate(id=name,pagesize=size,frames=[Frame(54,46,w-108,h-97,leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)],onPage=decorate))
story=[Spacer(1,50),p('Scalable web app<br/>on DigitalOcean Kubernetes','TitleMain')]
# rich() escapes HTML, so the title above is intentionally replaced by an explicit Paragraph.
story[-1]=Paragraph('Scalable web app<br/>on DigitalOcean Kubernetes',styles['TitleMain'])
story += [p('Technical Account Manager case study','H2x'),p('Pooja Singh | October 30, 2026'),Spacer(1,20),p('A small Node.js application with load distribution, pod autoscaling, a managed HA control plane, and a measured customer handoff.'),Spacer(1,14)]
story += table([['Deliverable','Included'],['Architecture','Illustrative scaled state; health-check and availability boundaries.'],['Setup and operations','Deployment, safe HPA migration, verification, troubleshooting, teardown.'],['Cost and performance','Explicit pricing assumptions and raw-backed endpoint benchmarks.'],['Quarterly business review','Two-page customer review with risks, owners, and next actions.'],['Evidence','Raw API/benchmark outputs, versions, tests, and dashboard screenshots.']])
story += [p('Source repository','H2x'),p('[github.com/pooja1909/do-k8s-scalable-webapp](https://github.com/pooja1909/do-k8s-scalable-webapp)'),p('Deployed release: 1.0.2. Public demo: http://137.184.244.5. The evidence includes endpoint benchmarks, a monitored rolling deployment, and controlled voluntary pod recovery.','Smallx')]
story += [NextPageTemplate('landscape'),PageBreak(),Image(str(ROOT/'docs/architecture.png'),width=684,height=444.6),NextPageTemplate('portrait'),PageBreak()]
for name in ['SETUP_GUIDE.md','COST_AND_PERFORMANCE.md','RELIABILITY.md','QBR_SUMMARY.md']:
    story+=markdown(ROOT/'docs'/name); story.append(PageBreak())
story+=markdown(ROOT/'evidence/README.md')
story += [PageBreak(),p('Technical and pricing references','H1x')]
refs=[
('Horizontal Pod Autoscaling and replica migration','https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/'),
('Topology spread constraints','https://kubernetes.io/docs/concepts/scheduling-eviction/topology-spread-constraints/'),
('Pod disruptions and PDB boundaries','https://kubernetes.io/docs/concepts/workloads/pods/disruptions/'),
('Service proxies and connection routing','https://kubernetes.io/docs/reference/networking/virtual-ips/'),
('DOKS Load Balancer settings and managed health checks','https://docs.digitalocean.com/products/kubernetes/how-to/configure-load-balancers/'),
('DOKS Cluster Autoscaler','https://docs.digitalocean.com/products/kubernetes/how-to/autoscale/'),
('doctl cluster creation flags','https://docs.digitalocean.com/reference/doctl/reference/kubernetes/cluster/create/'),
('DOKS pricing','https://docs.digitalocean.com/products/kubernetes/details/pricing/'),
('Droplet pricing','https://www.digitalocean.com/pricing/droplets'),
('Regional Load Balancer pricing','https://docs.digitalocean.com/products/networking/load-balancers/details/pricing/'),
('HA control-plane SLA','https://www.digitalocean.com/sla/doks')]
for i,(title,url) in enumerate(refs,1): story+=[p(f'{i}. [{title}]({url})'),p(url,'Smallx')]
story+=[p('Official references checked October 30, 2026. The evidence folder contains the actual observations; configuration documentation is not a substitute for measured application availability.','Smallx')]
for filename,title,caption in [
('cluster-ha.png','Dashboard evidence / high availability','The cluster list shows HA Enabled and Kubernetes 1.37.0-do.2. This verifies configuration, not application uptime.'),
('load-balancer-overview.png','Dashboard evidence / Load Balancer type and cost','Regional / External Network Load Balancer; dashboard estimate $15 per month. This is the Load Balancer used in the cost model.'),
('load-balancer-health-checks.png','Dashboard evidence / effective health checks','HTTP on port 10256 at /healthz: the node health endpoint, distinct from the app on port 8080.'),
('node-autoscaling.png','Dashboard evidence / node pool','Node pool autoscaling is enabled from 2 to 4 nodes. Actual node scale-out was not exercised in these benchmarks.')]:
    story += [NextPageTemplate('landscape'),PageBreak(),p(title,'H1x'),Image(str(ROOT/'evidence/screenshots'/filename),width=684,height=387.6),Spacer(1,10),p(caption,'Smallx')]
doc.build(story)
reader=PdfReader(OUT)
qbr=doc.sections['Quarterly Business Review']; evidence=doc.sections['Evidence Index']
if evidence-qbr != 2: raise RuntimeError(f'QBR is {evidence-qbr} pages; expected 2')
metadata={'pages':len(reader.pages),'section_pages':doc.sections,'qbr_pages':2,'pdf':str(OUT.relative_to(ROOT))}
(ROOT/'output/pdf/build-info.json').write_text(json.dumps(metadata,indent=2)+'\n')
print(json.dumps(metadata,indent=2))
