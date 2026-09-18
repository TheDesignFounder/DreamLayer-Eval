from .luma_photon_node import LumaPhotonDepth2Img

NODE_CLASS_MAPPINGS = {
    "LumaPhotonDepth2Img": LumaPhotonDepth2Img,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LumaPhotonDepth2Img": "Luma Photon (Depth)",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
