# Great A'Tuin jar stand. JAR is the jar's base diameter in mm (inches x 25.4).
PY      ?= .venv/bin/python
BLENDER ?= blender
JAR     ?= 152.4

.PHONY: all setup stl disc 3mf slice check renders

all: stl 3mf check renders

setup:
	python3 -m venv .venv
	$(PY) -m pip install -r requirements.txt

stl:
	$(PY) atuin.py --jar-diameter $(JAR)

disc:
	$(PY) atuin.py --jar-diameter $(JAR) --parts disc

3mf:
	$(PY) tools/make_3mf.py --jar-diameter $(JAR)

slice:
	$(PY) tools/make_3mf.py --jar-diameter $(JAR) --slice

check:
	$(PY) tools/check.py --jar-diameter $(JAR)

renders:
	$(BLENDER) -b -P tools/render.py -- --jar-diameter $(JAR) 2>&1 | grep -E "Saved|Error|Traceback"
