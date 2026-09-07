"""Shared plumbing and the GUI.

A real package, never a namespace one: `tools/` was only a namespace
package once, and a module-scope import of it killed the entire GUI --
invisibly, because under `gui.pyw` (pythonw, no console) the traceback
has nowhere to go and the window simply never appears.
"""
