"""Start the local worker if needed, then serve the private loopback workspace."""
import os
from pathlib import Path
import subprocess
import sys
from operations import Operations, state_root

ops=Operations()
if ops.status()['worker']=='offline':
    with (state_root()/'worker-launcher.log').open('a') as out:
        subprocess.Popen([sys.executable,str(Path(__file__).with_name('worker.py'))],stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
os.execv(sys.executable,[sys.executable,str(Path(__file__).with_name('production.py')),'--local',*sys.argv[1:]])
