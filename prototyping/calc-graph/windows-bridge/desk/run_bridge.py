"""Launcher for the bridge inside the signed-in desktop session (start.ps1 runs it with
pythonw from a one-shot `schtasks /it` task, so there is no console window and stdout/stderr
go to the log). ``run_bridge.py --port 8765 --log C:\\calcgraph\\logs\\bridge-....log``"""
import argparse
import os
import runpy
import sys

ap = argparse.ArgumentParser()
ap.add_argument("--port", default="8765")
ap.add_argument("--log", required=True)
a = ap.parse_args()
here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # C:\calcgraph\bridge
os.chdir(here)
sys.path.insert(0, here)
sys.stdout = sys.stderr = open(a.log, "a", buffering=1, encoding="utf-8")
sys.argv = ["calcgraph_bridge", "--port", str(a.port)]
runpy.run_module("calcgraph_bridge", run_name="__main__")
