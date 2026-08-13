import importlib.util
import os
import sys
import tempfile

_PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_PLUGIN_ROOT, "daemon"))
sys.path.insert(0, os.path.join(_PLUGIN_ROOT, "central_hub"))

# image_subscriber.py creates SAVED_IMAGES_DIR at import time (os.makedirs), so this must be
# set before any test module can trigger that import.
os.environ.setdefault("SAVED_IMAGES_DIR", tempfile.mkdtemp(prefix="ckn_mqtt_test_saved_images_"))


def _preload_daemon_script():
    """daemon/daemon.py shares its name with the daemon/ package (daemon/__init__.py, empty,
    just a package marker). Since ckn-mqtt-cameratraps/ itself has an __init__.py too, pytest's
    package-mode import machinery puts the plugin root on sys.path, and `import daemon` there
    resolves to the empty daemon/ package instead of the daemon/daemon.py script, regardless of
    our own sys.path.insert ordering above. Load the real script explicitly by path and register
    it in sys.modules under the plain name "daemon" so every test's `import daemon` finds it.
    """
    if "daemon" in sys.modules and hasattr(sys.modules["daemon"], "tail_and_process_events"):
        return
    script_path = os.path.join(_PLUGIN_ROOT, "daemon", "daemon.py")
    spec = importlib.util.spec_from_file_location("daemon", script_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["daemon"] = module
    spec.loader.exec_module(module)


_preload_daemon_script()
