"""The converter window, split out of the former monolithic gui.py.

Root `gui.py` is now only a launcher. Modules here take a `GuiApp`
carrier (see `app.py`) rather than closing over one builder function's
scope, which is what let the window be split at all.
"""
