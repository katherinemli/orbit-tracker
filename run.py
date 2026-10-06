"""Start the daemon and the API together. Ctrl+C stops both."""

import subprocess
import sys

procs = [
    subprocess.Popen([sys.executable, "-m", "tracker.daemon", "--autostart"]),
    subprocess.Popen([sys.executable, "-m", "api.server"]),
]
try:
    for p in procs:
        p.wait()
except KeyboardInterrupt:
    for p in procs:
        p.terminate()
