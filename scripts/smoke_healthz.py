import importlib
m = importlib.import_module("healthz")
assert hasattr(m, "router") or hasattr(m, "r")
print("healthz import OK:", m.__file__)