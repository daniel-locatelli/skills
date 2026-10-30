# BIM skills

Skills that turn design geometry into building information. `converting-rhino-to-ifc4`
classifies the layers of a non-BIM Rhino model into IFC classes (the agent decides,
from layer names and measured shape) and writes IFC4 offline with rhino3dm and
ifcopenshell. Tests: `.venv/Scripts/python -m pytest skills/bim/converting-rhino-to-ifc4/tests -v`
(`pip install -r skills/bim/converting-rhino-to-ifc4/requirements.txt` first).
