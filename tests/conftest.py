import sys
from pathlib import Path

# las herramientas se importan como módulos sueltos (igual que entre ellas)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "herramientas"))
