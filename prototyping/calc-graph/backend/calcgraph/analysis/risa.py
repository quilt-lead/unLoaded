"""RISA-3D adapter - stub. Not built in the prototype; ETABS (etabs.py) is the reference adapter."""
from __future__ import annotations

from .base import AnalysisAdapter

_MSG = ("RISA adapter is not implemented in this prototype - only the ETABS adapter "
        "(calcgraph.analysis.etabs) exists; use get_adapter('etabs').")


class RisaAdapter(AnalysisAdapter):
    name = "RISA-3D"
    doc = "risa"

    def __init__(self, design=None):
        self.design = design

    def model_objects(self):
        raise NotImplementedError(_MSG)

    def occurrences(self):
        raise NotImplementedError(_MSG)

    def export_model(self, path, design=None, change=None, redesign=False):
        raise NotImplementedError(_MSG)

    def send_change(self, design, change):
        raise NotImplementedError(_MSG)

    def pull_results(self, job):
        raise NotImplementedError(_MSG)
