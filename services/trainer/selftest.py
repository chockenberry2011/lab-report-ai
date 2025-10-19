#!/usr/bin/env python3
"""
Self-test for trainer package imports

Tests that all trainer modules can be imported successfully to catch
import issues during build/deployment.
"""

def main():
    import importlib
    mods = [
        "services.trainer.roles.prep_roles",
        "services.trainer.roles.train_roles",
        "services.trainer.roles.eval_roles",
        "services.trainer.testrow.prep_testrow",
        "services.trainer.testrow.train_testrow",
        "services.trainer.testrow.eval_testrow",
    ]
    for m in mods:
        importlib.import_module(m)
    print("OK: imported", len(mods), "modules")

if __name__ == "__main__":
    main()