import json
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ipad_usb_monitor.usb import run
from ipad_usb_monitor.paths import STATE

name = sys.argv[1]
base = Path(__file__).resolve().parent
unit = 'ipad2-k94-motion-' + str(int(time.time()))
output,status=run('/bin/busybox touch /run/k94-profile; /bin/busybox pkill -f "^/run/fbvnc " || true')
if status:raise RuntimeError(output)
time.sleep(3)
subprocess.run(['systemd-run','--user','--unit='+unit,'--collect','--service-type=exec',
    '/usr/bin/mpv','--no-config','--no-audio','--force-window=yes','--focus-on=never',
    '--screen-name=IPAD2','--fs-screen-name=IPAD2','--fullscreen','--length=14',
    '--vo=gpu','--gpu-context=wayland','--no-osc','--osd-level=0','--title=IPAD2-PERF',
    'av://lavfi:testsrc2=size=1024x768:rate=60'],check=True)
samples=[]
try:
    time.sleep(2)
    clients=json.loads(subprocess.check_output(['hyprctl','-i','0','clients','-j'],text=True))
    monitors=json.loads(subprocess.check_output(['hyprctl','-i','0','monitors','-j'],text=True))
    monitor=next(m for m in monitors if m['name']=='IPAD2')
    for client in clients:
        if client.get('title')=='IPAD2-PERF' and client['monitor']!=monitor['id']:
            subprocess.run(['hyprctl','-i','0','dispatch','movetoworkspacesilent',
                str(monitor['activeWorkspace']['id'])+',address:'+client['address']],check=True)
    for i in range(5):
        time.sleep(2)
        output,status=run('cat /run/k94-vnc-perf')
        if status:raise RuntimeError(output)
        sample={k:float(v) for k,v in (item.split('=') for item in output.split())}
        samples.append(sample)
        print(json.dumps(sample),flush=True)
finally:
    subprocess.run(['systemctl','--user','stop',unit+'.service'],check=False)
    run('/bin/busybox rm -f /run/k94-profile; /bin/busybox pkill -f "^/run/fbvnc " || true')
destination=STATE/'display-perf-results.json'
results=json.loads(destination.read_text()) if destination.exists() else {}
results[name]=samples
destination.write_text(json.dumps(results,indent=2)+'\n')
