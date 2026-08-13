import os
import sys

_PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PLUGIN_ROOT)

# model.py builds a real HFTransformerVisionLLM (downloads a HF model) at import time when
# MODEL_TYPE defaults to "vision_transformer". Force the lightweight ImageNetModel branch
# before anything in this test session can trigger that import.
os.environ.setdefault("MODEL_TYPE", "imagenet")

# ImageNetModel.__init__ also runs at that same import time and opens IMAGENET_CLASSES_PATH
# (default: a relative "imagenet_classes.txt", relative to the process CWD, not this plugin's
# directory) -- point it at the real file so import doesn't fail with FileNotFoundError when
# pytest is invoked from the repo root.
os.environ.setdefault(
    "IMAGENET_CLASSES_PATH", os.path.join(_PLUGIN_ROOT, "imagenet_classes.txt")
)
