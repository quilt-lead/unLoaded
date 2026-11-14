"""calc-graph Windows bridge: BHoM + CSI OAPI behind a loopback-only FastAPI service.

Runs on an office Windows desk, never on the Mac. The Mac reaches it through
``ssh -L 8765:127.0.0.1:8765 <desk>``; the service binds 127.0.0.1 only.
Every response names its source so the Mac side can label each value
(real ETABS via BHoM / real CSI OAPI / not installed).
"""

__version__ = "0.1.0"
