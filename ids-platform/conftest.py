"""
Ensures the project root is importable as `backend.*` no matter where pytest
is invoked from. This avoids needing an editable install just to run tests.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
