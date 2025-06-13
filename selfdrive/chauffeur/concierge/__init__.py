"""
Concierge – lightweight web console for Chauffeur
"""
from importlib.metadata import version, PackageNotFoundError
try:
    __version__ = version("concierge")
except PackageNotFoundError:  # dev editable install
    __version__ = "0.0.0"