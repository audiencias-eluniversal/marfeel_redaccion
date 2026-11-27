import os,subprocess
BS=chr(92)
m={'a7b0f0dc11ce528f9490eab9f0824428':'eu_rojo.svg','8a1b90aa65788acbc91678ae1d9a48e8':'native_ad.png','7dc026b1ba87c225b9a0574a9ab2cf94':'native_ad_zoom.png','cfcabc97798cd057417101eb2844a66c':'post_fb.jpg','df8003a8fa587e56b0887c55f3580508':'captura_nota.png'}
css=open('_deck/project/deck.css',encoding='utf8').read()
edge="C:"+BS+"Program Files (x86)"+BS+"Microsoft"+BS+"Edge"+BS+"Application"+BS+"msedge.exe"
base=os.getcwd().replace(BS,'/')
for n in ['native','facebook','metricas']:
    s=open('_deck/project/slides/'+n+'.html',encoding='utf8').read()
    for k,v in m.items(): s=s.replace('/_blob/'+k,'../_assets_deck/'+v)
    pre='<!doctype html><meta charset=utf8><style>body{margin:0}p,h1,h2,h3{margin:0}aside{display:none}'+css+'section{width:1920px;height:1080px;box-sizing:border-box;position:relative;overflow:hidden}</style>'
    open('_preview/'+n+'.html','w',encoding='utf8').write(pre+s)
    subprocess.run([edge,'--headless','--screenshot='+base+'/_preview/'+n+'.png','--window-size=1920,1080','file:///'+base+'/_preview/'+n+'.html'],capture_output=True)
