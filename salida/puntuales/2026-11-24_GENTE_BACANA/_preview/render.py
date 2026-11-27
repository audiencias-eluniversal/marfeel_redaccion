import glob,os,subprocess
BS=chr(92)
m={'506c35306e9350c263218e68fb314013':'eu_rojo.svg','a0784488495f36964537a7ad7afa8b8f':'eu_blanco.svg','35862562e6cedddf1cf132570fa2751b':'gente_bacana.png','80d0dd551d3dd5987829d03fe88f0c3e':'afinia_blanco.png','6796b90f2f22aeb773825dcc32dea05a':'afinia.png','1ef171e3d710b78ef47d60d7f7d6131c':'foto_grupo.jpg','9cf43b21ed747f2e97433ad0189e0dce':'foto_ninos.jpg','f26cebe67947310d3c3d281232b42be5':'foto_lideres.jpg','25a061f09bb851deb39eef76267c5e90':'foto_cartilla.jpg','f9a6205026be92cfa574a6a5aaf9799a':'foto_tecnico.jpg'}
css=open('_deck/project/deck.css',encoding='utf8').read()
edge="C:"+BS+"Program Files (x86)"+BS+"Microsoft"+BS+"Edge"+BS+"Application"+BS+"msedge.exe"
base=os.getcwd().replace(BS,'/')
for f in glob.glob('_deck/project/slides/*.html'):
    n=os.path.basename(f)[:-5]; s=open(f,encoding='utf8').read()
    for k,v in m.items(): s=s.replace('/_blob/'+k,'../_assets_deck/'+v)
    pre='<!doctype html><meta charset=utf8><style>body{margin:0}p,h1,h2,h3{margin:0}aside{display:none}table{border-collapse:collapse}td,th{text-align:left;padding:0.35em 0.6em;border-bottom:1px solid #ddd}'+css+'section{width:1920px;height:1080px;box-sizing:border-box;position:relative;overflow:hidden}</style>'
    open('_preview/'+n+'.html','w',encoding='utf8').write(pre+s)
    subprocess.run([edge,'--headless','--screenshot='+base+'/_preview/'+n+'.png','--window-size=1920,1080','file:///'+base+'/_preview/'+n+'.html'],capture_output=True)
print(sorted(os.listdir('_preview')))
