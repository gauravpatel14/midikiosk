import sys
import backend.database
from backend.database import Base, get_db, init_db

sys.modules[__name__] = backend.database

__all__ = ["Base", "get_db", "init_db"]
