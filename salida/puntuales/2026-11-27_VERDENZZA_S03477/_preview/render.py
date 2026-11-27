import os,subprocess,glob
BS=chr(92)
m={'06f1c4e684494fe4493681f417592939':'verdenzza_logo.svg','56379cc0d38a829961b66700cd9b115e':'verdenzza_logo_blanco.svg','d1c774ab617119b7b78109873bf4b49a':'eu_rojo.svg','8a811a2ba45b6625839c375c940a4597':'eu_blanco.svg','3d8b7676331d3365fa6da683c806b80f':'m_feed.jpg','f1c25ca0293cd46d00d038132310a9a2':'m_vertical.jpg','1af46ff2aba17364477c052c550b035d':'b_728x90.png','b1a450d785289e2912d9a8c60dd10392':'b_300x600.png','26fe1739ba7baf2ff71dd0bc994dd165':'b_970x250.png','820cacc4abb84bc99f990e4ade01ee47':'b_320x100.jpg','af5d9ebda17f72d9117b016091763fb4':'b_300x250.jpg'}
css=open('_deck/project/deck.css',encoding='utf8').read()
edge="C:"+BS+"Program Files (x86)"+BS+"Microsoft"+BS+"Edge"+BS+"Application"+BS+"msedge.exe"
base=os.getcwd().replace(BS,'/')
for f in glob.glob('_deck/project/slides/*.html'):
    n=os.path.basename(f)[:-5]; s=open(f,encoding='utf8').read()
    for k,v in m.items(): s=s.replace('/_blob/'+k,'../_assets_deck/'+v)
    pre='<!doctype html><meta charset=utf8><style>body{margin:0}p,h1,h2,h3{margin:0}aside{display:none}'+css+'section{width:1920px;height:1080px;box-sizing:border-box;position:relative;overflow:hidden}</style>'
    open('_preview/'+n+'.html','w',encoding='utf8').write(pre+s)
    subprocess.run([edge,'--headless','--screenshot='+base+'/_preview/'+n+'.png','--window-size=1920,1080','file:///'+base+'/_preview/'+n+'.html'],capture_output=True)
