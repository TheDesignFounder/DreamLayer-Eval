import torch
import os

# Define a predictable directory for the cache within the workspace
# This path should be relative to the repository root.
script_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.dirname(script_dir)
torch_hub_dir = os.path.join(repo_root, 'torch_hub_cache')
os.environ['TORCH_HOME'] = torch_hub_dir
os.makedirs(torch_hub_dir, exist_ok=True)

print(f"Setting TORCH_HOME to: {torch_hub_dir}")
print("Downloading MiDaS model and transforms...")

# Note: trust_repo=True allows executing code from the repository.
# This is required for loading models from PyTorch Hub but should be used cautiously.
# Load the model and transforms to trigger the download
try:
    torch.hub.load("intel-isl/MiDaS", "MiDaS_small", trust_repo=True)
    torch.hub.load("intel-isl/MiDaS", "transforms", trust_repo=True)
except Exception as e:
    print(f"Failed to load from default source: {e}")
    # Fallback to github source if the default fails
    torch.hub.load("intel-isl/MiDaS", "MiDaS_small", source='github', trust_repo=True)
    torch.hub.load("intel-isl/MiDaS", "transforms", source='github', trust_repo=True)

print("MiDaS model downloaded successfully.")
