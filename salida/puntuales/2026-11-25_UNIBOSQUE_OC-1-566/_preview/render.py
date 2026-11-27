import os,subprocess,glob
BS=chr(92)
m={'2e3920cef60abfbd84d775b83f1765b2':'unbosque_logo.svg','a7ece8df9b5b4fea0644760e6667685d':'unbosque_logo_blanco.svg','ba09e9da64d24e7691f4bd6793709488':'eu_rojo.svg','bd95a4908856e18583f1986e7c29892b':'eu_blanco.svg','886f974a205e6d87e1c6899097573b8d':'d_vertical.png','455648075d28525d044e57b6c4ff13dd':'d_billboard.png','d718a752d2827bf149eb54663f572e9e':'d_leaderboard.png','3c5ad9d465942cb2ecfbe5dde31c2470':'m_rectangulo.jpg','c81f01730e06259cde361e49d7b851e3':'m_movil.jpg','9e402136fe7c82040d89caffeb8c28c5':'crop_vertical.png','1a92bf1fb873791e834b2ecc47c97675':'crop_billboard.png','6839c37e6cb432c37150ef5ac183318a':'crop_leaderboard.png'}
css=open('_deck/project/deck.css',encoding='utf8').read()
edge="C:"+BS+"Program Files (x86)"+BS+"Microsoft"+BS+"Edge"+BS+"Application"+BS+"msedge.exe"
base=os.getcwd().replace(BS,'/')
for f in glob.glob('_deck/project/slides/*.html'):
    n=os.path.basename(f)[:-5]; s=open(f,encoding='utf8').read()
    for k,v in m.items(): s=s.replace('/_blob/'+k,'../_assets_deck/'+v)
    pre='<!doctype html><meta charset=utf8><style>body{margin:0}p,h1,h2,h3{margin:0}aside{display:none}'+css+'section{width:1920px;height:1080px;box-sizing:border-box;position:relative;overflow:hidden}</style>'
    open('_preview/'+n+'.html','w',encoding='utf8').write(pre+s)
    subprocess.run([edge,'--headless','--screenshot='+base+'/_preview/'+n+'.png','--window-size=1920,1080','file:///'+base+'/_preview/'+n+'.html'],capture_output=True)
