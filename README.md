# PiCycle
Raspberry Pi based bicycle computer

Features:
1. Read and display wheel speed from a Hall effect sensor - done
2. Calculate distance - done
3. Record workout metrics (distance, max and average speed, time, ...)
4. Local lcd display - done
5. Web interface - done
6. Allow input of session goals (create options for different preset sessions, and track progress during the ride.
7. Also use for a treadmill?
8. Input device for local display (buttons or rotary) - done
9. Multiple users.
10. 

## Development setup

PiCycle is being revamped as an offline-first Raspberry Pi workout appliance. The
on-bike display is the cockpit; the web UI is the workshop.

Create a virtual environment, then install the desktop/prototype dependency set:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -U pip
.\.venv\Scripts\python -m pip install -e .[prototype]
```

On Raspberry Pi hardware, install the hardware extra in that environment:

```bash
python -m pip install -e '.[hardware]'
```

The first local smoke gate checks that dependency groups are declared and reports which
imports are available. It does not require Raspberry Pi GPIO/display libraries:

```powershell
python tools\smoke_imports.py
```

After installing desktop/prototype dependencies, run the strict check:

```powershell
python tools\smoke_imports.py --strict-installed
```

Hardware imports are intentionally optional for desktop development. Use
`--include-hardware` with `--strict-installed` only on the Raspberry Pi.

Prototype mode can be selected without editing source:

```powershell
$env:PICYCLE_HARDWARE = "prototype"
$env:PICYCLE_DISPLAY = "headless"
python tools\prototype_smoke.py
```

`PICYCLE_HARDWARE` accepts `real`/`hardware`/`true` or `prototype`/`false` style values.
`PICYCLE_DISPLAY` accepts `auto`, `headless`, `prototype`, or `ili9341`.

Run the storage tests:

```powershell
python -m unittest discover -s tests
```

Run the single-process prototype runtime smoke:

```powershell
$env:PICYCLE_HARDWARE = "prototype"
$env:PICYCLE_DISPLAY = "headless"
python tools\runtime_smoke.py
```

Run all current software gates:

```powershell
python tools\smoke_imports.py
$env:PICYCLE_DISPLAY = "headless"
python tools\prototype_smoke.py
$env:PICYCLE_HARDWARE = "prototype"
python tools\runtime_smoke.py
python -m unittest discover -s tests
```
