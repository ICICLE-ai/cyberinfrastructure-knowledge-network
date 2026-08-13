import os
import sys
from unittest.mock import MagicMock

_EDGE_SERVER_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _EDGE_SERVER_ROOT)

# server_utils.py and server.py both do `from model import predict, pre_process, model_store`.
# The real model.py runs `torch.hub.load('pytorch/vision:v0.10.0', 'resnet152', pretrained=True)`
# as a live statement inside the ModelStore class body -- not inside a method -- so it executes
# the instant the class is defined, i.e. at import time, downloading a real model regardless of
# whether ModelStore() is ever instantiated. model.py also opens imagenet_classes.txt at module
# level via a relative path. Stub the whole module out in sys.modules before anything in this
# test session can trigger that import.
_fake_model_module = MagicMock(name="model")
sys.modules.setdefault("model", _fake_model_module)
