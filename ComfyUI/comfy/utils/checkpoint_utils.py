import torch
import comfy.checkpoint_pickle
import safetensors.torch
import logging
from comfy.cli_args import args

MMAP_TORCH_FILES = args.mmap_torch_files
ALWAYS_SAFE_LOAD = False
if hasattr(torch.serialization, "add_safe_globals"):  
    class ModelCheckpoint:
        pass
    ModelCheckpoint.__module__ = "pytorch_lightning.callbacks.model_checkpoint"

    from numpy.core.multiarray import scalar
    from numpy import dtype
    from numpy.dtypes import Float64DType
    from _codecs import encode

    torch.serialization.add_safe_globals([ModelCheckpoint, scalar, dtype, Float64DType, encode])
    ALWAYS_SAFE_LOAD = True
    logging.info("Checkpoint files will always be loaded safely.")
else:
    logging.info("Warning, you are using an old pytorch version and some ckpt/pt files might be loaded unsafely. Upgrading to 2.4 or above is recommended.")

def load_torch_file(ckpt, safe_load=False, device=None, return_metadata=False):
    if device is None:
        device = torch.device("cpu")
    metadata = None
    if ckpt.lower().endswith(".safetensors") or ckpt.lower().endswith(".sft"):
        try:
            with safetensors.safe_open(ckpt, framework="pt", device=device.type) as f:
                sd = {}
                for k in f.keys():
                    sd[k] = f.get_tensor(k)
                if return_metadata:
                    metadata = f.metadata()
        except Exception as e:
            if len(e.args) > 0:
                message = e.args[0]
                if "HeaderTooLarge" in message:
                    raise ValueError(f"{message}\n\nFile path: {ckpt}\n\nThe safetensors file is corrupt or invalid. Make sure this is actually a safetensors file and not a ckpt or pt or other filetype.")
                if "MetadataIncompleteBuffer" in message:
                    raise ValueError(f"{message}\n\nFile path: {ckpt}\n\nThe safetensors file is corrupt/incomplete. Check the file size and make sure you have copied/downloaded it correctly.")
            raise e
    else:
        torch_args = {}
        if MMAP_TORCH_FILES:
            torch_args["mmap"] = True

        if safe_load or ALWAYS_SAFE_LOAD:
            pl_sd = torch.load(ckpt, map_location=device, weights_only=True, **torch_args)
        else:
            pl_sd = torch.load(ckpt, map_location=device, pickle_module=comfy.checkpoint_pickle)
        if "state_dict" in pl_sd:
            sd = pl_sd["state_dict"]
        else:
            if len(pl_sd) == 1:
                key = list(pl_sd.keys())[0]
                sd = pl_sd[key]
                if not isinstance(sd, dict):
                    sd = pl_sd
            else:
                sd = pl_sd
    return (sd, metadata) if return_metadata else sd

def save_torch_file(sd, ckpt, metadata=None):
    if metadata is not None:
        safetensors.torch.save_file(sd, ckpt, metadata=metadata)
    else:
        safetensors.torch.save_file(sd, ckpt)

def calculate_parameters(sd, prefix=""):
    params = 0
    for k in sd.keys():
        if k.startswith(prefix):
            w = sd[k]
            params += w.nelement()
    return params

def weight_dtype(sd, prefix=""):
    dtypes = {}
    for k in sd.keys():
        if k.startswith(prefix):
            w = sd[k]
            dtypes[w.dtype] = dtypes.get(w.dtype, 0) + w.numel()

    if len(dtypes) == 0:
        return None

    return max(dtypes, key=dtypes.get)

def state_dict_key_replace(state_dict, keys_to_replace):
    for x in keys_to_replace:
        if x in state_dict:
            state_dict[keys_to_replace[x]] = state_dict.pop(x)
    return state_dict

def state_dict_prefix_replace(state_dict, replace_prefix, filter_keys=False):
    if filter_keys:
        out = {}
    else:
        out = state_dict
    for rp in replace_prefix:
        replace = list(map(lambda a: (a, f"{replace_prefix[rp]}{a[len(rp):]}"), filter(lambda a: a.startswith(rp), state_dict.keys())))
        for x in replace:
            w = state_dict.pop(x[0])
            out[x[1]] = w
    return out 