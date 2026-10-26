"""Replace only the existing synthetic API, preserving private data and fixed IP."""
import json
from pathlib import Path
import subprocess
import time
import urllib.request

root=Path(__file__).resolve().parent
private=root/'private'
manifest=json.loads((private/'manifest.json').read_text())
assert manifest['mode']=='synthetic-staging' and manifest['providerConnections']==0
image='onecli-owner-isolation:cached-auth-20261026'
name='oxfa-boundary-api'
rollback='oxfa-boundary-api-before-cached-auth'
def run(*args):
    return subprocess.run(args,check=True,capture_output=True,text=True).stdout
old=json.loads(run('docker','inspect',name))[0]
assert old['Config']['Image']=='onecli-owner-isolation:e0ca80e','Refusing unexpected or already upgraded candidate'
new_image=json.loads(run('docker','image','inspect',image))[0]['Id']
ip=old['NetworkSettings']['Networks']['oxfa-boundary-backend']['IPAddress']
assert ip==json.loads((private/'firewall.json').read_text())['apiIP']
assert len(old['Mounts'])==1 and old['Mounts'][0]['Type']=='volume' and old['Mounts'][0]['Destination']=='/app/data'
volume=old['Mounts'][0]['Name']
assert subprocess.run(['docker','inspect',rollback],capture_output=True).returncode!=0
run('docker','stop',name)
run('docker','rename',name,rollback)
try:
    run('docker','network','disconnect','oxfa-boundary-backend',rollback)
    run('docker','run','-d','--name',name,'--network','oxfa-boundary-backend','--ip',ip,
        '--memory','3g','--cpus','2','--cap-drop','ALL','--security-opt','no-new-privileges',
        '--env-file',str(private/'app.env'),'--mount',f'type=volume,src={volume},dst=/app/data',image)
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for _ in range(90):
        try:
            with opener.open(f'http://{ip}:10254/v1/health',timeout=2) as response:
                if response.status==200:break
        except Exception:pass
        time.sleep(1)
    else:raise RuntimeError('Updated staged API failed health check')
except Exception:
    subprocess.run(['docker','rm','-f',name],capture_output=True)
    current=json.loads(run('docker','inspect',rollback))[0]
    if 'oxfa-boundary-backend' not in current['NetworkSettings']['Networks']:
        run('docker','network','connect','--ip',ip,'oxfa-boundary-backend',rollback)
    run('docker','rename',rollback,name)
    run('docker','start',name)
    raise
receipt={'mode':'synthetic-staging','previousImage':old['Image'],'image':new_image,
         'fixedIPPreserved':True,'privateVolumePreserved':True,'health':'passed','productionChanges':False}
(root/'upgrade-results.json').write_text(json.dumps(receipt,indent=2))
print(json.dumps(receipt))
