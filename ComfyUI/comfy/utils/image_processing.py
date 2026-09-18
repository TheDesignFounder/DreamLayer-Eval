import torch
import numpy as np
from PIL import Image
from einops import rearrange
from torch.nn.functional import interpolate
import math
import itertools

def bislerp(samples, width, height):
    def slerp(b1, b2, r):
        c = b1.shape[-1]
        b1_norms = torch.norm(b1, dim=-1, keepdim=True)
        b2_norms = torch.norm(b2, dim=-1, keepdim=True)
        b1_normalized = b1 / b1_norms
        b2_normalized = b2 / b2_norms
        b1_normalized[b1_norms.expand(-1,c) == 0.0] = 0.0
        b2_normalized[b2_norms.expand(-1,c) == 0.0] = 0.0
        dot = (b1_normalized*b2_normalized).sum(1)
        omega = torch.acos(dot)
        so = torch.sin(omega)
        res = (torch.sin((1.0-r.squeeze(1))*omega)/so).unsqueeze(1)*b1_normalized + (torch.sin(r.squeeze(1)*omega)/so).unsqueeze(1) * b2_normalized
        res *= (b1_norms * (1.0-r) + b2_norms * r).expand(-1,c)
        res[dot > 1 - 1e-5] = b1[dot > 1 - 1e-5]
        res[dot < 1e-5 - 1] = (b1 * (1.0-r) + b2 * r)[dot < 1e-5 - 1]
        return res
    def generate_bilinear_data(length_old, length_new, device):
        coords_1 = torch.arange(length_old, dtype=torch.float32, device=device).reshape((1,1,1,-1))
        coords_1 = torch.nn.functional.interpolate(coords_1, size=(1, length_new), mode="bilinear")
        ratios = coords_1 - coords_1.floor()
        coords_1 = coords_1.to(torch.int64)
        coords_2 = torch.arange(length_old, dtype=torch.float32, device=device).reshape((1,1,1,-1)) + 1
        coords_2[:,:,:,-1] -= 1
        coords_2 = torch.nn.functional.interpolate(coords_2, size=(1, length_new), mode="bilinear")
        coords_2 = coords_2.to(torch.int64)
        return ratios, coords_1, coords_2
    orig_dtype = samples.dtype
    samples = samples.float()
    n,c,h,w = samples.shape
    h_new, w_new = (height, width)
    ratios, coords_1, coords_2 = generate_bilinear_data(w, w_new, samples.device)
    coords_1 = coords_1.expand((n, c, h, -1))
    coords_2 = coords_2.expand((n, c, h, -1))
    ratios = ratios.expand((n, 1, h, -1))
    pass_1 = samples.gather(-1,coords_1).movedim(1, -1).reshape((-1,c))
    pass_2 = samples.gather(-1,coords_2).movedim(1, -1).reshape((-1,c))
    ratios = ratios.movedim(1, -1).reshape((-1,1))
    result = slerp(pass_1, pass_2, ratios)
    result = result.reshape(n, h, w_new, c).movedim(-1, 1)
    ratios, coords_1, coords_2 = generate_bilinear_data(h, h_new, samples.device)
    coords_1 = coords_1.reshape((1,1,-1,1)).expand((n, c, -1, w_new))
    coords_2 = coords_2.reshape((1,1,-1,1)).expand((n, c, -1, w_new))
    ratios = ratios.reshape((1,1,-1,1)).expand((n, 1, -1, w_new))
    pass_1 = result.gather(-2,coords_1).movedim(1, -1).reshape((-1,c))
    pass_2 = result.gather(-2,coords_2).movedim(1, -1).reshape((-1,c))
    ratios = ratios.movedim(1, -1).reshape((-1,1))
    result = slerp(pass_1, pass_2, ratios)
    result = result.reshape(n, h_new, w_new, c).movedim(-1, 1)
    return result.to(orig_dtype)

def lanczos(samples, width, height):
    images = [Image.fromarray(np.clip(255. * image.movedim(0, -1).cpu().numpy(), 0, 255).astype(np.uint8)) for image in samples]
    images = [image.resize((width, height), resample=Image.Resampling.LANCZOS) for image in images]
    images = [torch.from_numpy(np.array(image).astype(np.float32) / 255.0).movedim(-1, 0) for image in images]
    result = torch.stack(images)
    return result.to(samples.device, samples.dtype)

def common_upscale(samples, width, height, upscale_method, crop):
    orig_shape = tuple(samples.shape)
    if len(orig_shape) > 4:
        samples = samples.reshape(samples.shape[0], samples.shape[1], -1, samples.shape[-2], samples.shape[-1])
        samples = samples.movedim(2, 1)
        samples = samples.reshape(-1, orig_shape[1], orig_shape[-2], orig_shape[-1])
    if crop == "center":
        old_width = samples.shape[-1]
        old_height = samples.shape[-2]
        old_aspect = old_width / old_height
        new_aspect = width / height
        x = 0
        y = 0
        if old_aspect > new_aspect:
            x = round((old_width - old_width * (new_aspect / old_aspect)) / 2)
        elif old_aspect < new_aspect:
            y = round((old_height - old_height * (old_aspect / new_aspect)) / 2)
        s = samples.narrow(-2, y, old_height - y * 2).narrow(-1, x, old_width - x * 2)
    else:
        s = samples
    if upscale_method == "bislerp":
        out = bislerp(s, width, height)
    elif upscale_method == "lanczos":
        out = lanczos(s, width, height)
    else:
        out = torch.nn.functional.interpolate(s, size=(height, width), mode=upscale_method)
    if len(orig_shape) == 4:
        return out
    out = out.reshape((orig_shape[0], -1, orig_shape[1]) + (height, width))
    return out.movedim(2, 1).reshape(orig_shape[:-2] + (height, width))

def get_tiled_scale_steps(width, height, tile_x, tile_y, overlap):
    rows = 1 if height <= tile_y else math.ceil((height - overlap) / (tile_y - overlap))
    cols = 1 if width <= tile_x else math.ceil((width - overlap) / (tile_x - overlap))
    return rows * cols

@torch.inference_mode()
def tiled_scale_multidim(samples, function, tile=(64, 64), overlap=8, upscale_amount=4, out_channels=3, output_device="cpu", downscale=False, index_formulas=None, pbar=None):
    dims = len(tile)
    if not (isinstance(upscale_amount, (tuple, list))):
        upscale_amount = [upscale_amount] * dims
    if not (isinstance(overlap, (tuple, list))):
        overlap = [overlap] * dims
    if index_formulas is None:
        index_formulas = upscale_amount
    if not (isinstance(index_formulas, (tuple, list))):
        index_formulas = [index_formulas] * dims
    def get_upscale(dim, val):
        up = upscale_amount[dim]
        if callable(up):
            return up(val)
        else:
            return up * val
    def get_downscale(dim, val):
        up = upscale_amount[dim]
        if callable(up):
            return up(val)
        else:
            return val / up
    def get_upscale_pos(dim, val):
        up = index_formulas[dim]
        if callable(up):
            return up(val)
        else:
            return up * val
    def get_downscale_pos(dim, val):
        up = index_formulas[dim]
        if callable(up):
            return up(val)
        else:
            return val / up
    if downscale:
        get_scale = get_downscale
        get_pos = get_downscale_pos
    else:
        get_scale = get_upscale
        get_pos = get_upscale_pos
    def mult_list_upscale(a):
        out = []
        for i in range(len(a)):
            out.append(round(get_scale(i, a[i])))
        return out
    output = torch.empty([samples.shape[0], out_channels] + mult_list_upscale(samples.shape[2:]), device=output_device)
    for b in range(samples.shape[0]):
        s = samples[b:b+1]
        if all(s.shape[d+2] <= tile[d] for d in range(dims)):
            output[b:b+1] = function(s).to(output_device)
            if pbar is not None:
                pbar.update(1)
            continue
        out = torch.zeros([s.shape[0], out_channels] + mult_list_upscale(s.shape[2:]), device=output_device)
        out_div = torch.zeros([s.shape[0], out_channels] + mult_list_upscale(s.shape[2:]), device=output_device)
        positions = [range(0, s.shape[d+2] - overlap[d], tile[d] - overlap[d]) if s.shape[d+2] > tile[d] else [0] for d in range(dims)]
        for it in itertools.product(*positions):
            s_in = s
            upscaled = []
            for d in range(dims):
                pos = max(0, min(s.shape[d + 2] - overlap[d], it[d]))
                l = min(tile[d], s.shape[d + 2] - pos)
                s_in = s_in.narrow(d + 2, pos, l)
                upscaled.append(round(get_pos(d, pos)))
            ps = function(s_in).to(output_device)
            mask = torch.ones_like(ps)
            for d in range(2, dims + 2):
                feather = round(get_scale(d - 2, overlap[d - 2]))
                if feather >= mask.shape[d]:
                    continue
                for t in range(feather):
                    a = (t + 1) / feather
                    mask.narrow(d, t, 1).mul_(a)
                    mask.narrow(d, mask.shape[d] - 1 - t, 1).mul_(a)
            o = out
            o_d = out_div
            for d in range(dims):
                o = o.narrow(d + 2, upscaled[d], mask.shape[d + 2])
                o_d = o_d.narrow(d + 2, upscaled[d], mask.shape[d + 2])
            o.add_(ps * mask)
            o_d.add_(mask)
            if pbar is not None:
                pbar.update(1)
        output[b:b+1] = out/out_div
    return output

def tiled_scale(samples, function, tile_x=64, tile_y=64, overlap = 8, upscale_amount = 4, out_channels = 3, output_device="cpu", pbar = None):
    return tiled_scale_multidim(samples, function, (tile_y, tile_x), overlap=overlap, upscale_amount=upscale_amount, out_channels=out_channels, output_device=output_device, pbar=pbar)

def reshape_mask(input_mask, output_shape):
    dims = len(output_shape) - 2
    if dims == 1:
        scale_mode = "linear"
    if dims == 2:
        input_mask = input_mask.reshape((-1, 1, input_mask.shape[-2], input_mask.shape[-1]))
        scale_mode = "bilinear"
    if dims == 3:
        if len(input_mask.shape) < 5:
            input_mask = input_mask.reshape((1, 1, -1, input_mask.shape[-2], input_mask.shape[-1]))
        scale_mode = "trilinear"
    mask = torch.nn.functional.interpolate(input_mask, size=output_shape[2:], mode=scale_mode)
    if mask.shape[1] < output_shape[1]:
        mask = mask.repeat((1, output_shape[1]) + (1,) * dims)[:,:output_shape[1]]
    mask = repeat_to_batch_size(mask, output_shape[0])
    return mask

def upscale_dit_mask(mask: torch.Tensor, img_size_in, img_size_out):
    hi, wi = img_size_in
    ho, wo = img_size_out
    if (hi, wi) == (ho, wo):
        return mask
    if mask.ndim == 2:
        mask = mask.unsqueeze(0)
    if mask.ndim != 3:
        raise ValueError(f"Got a mask of shape {list(mask.shape)}, expected [b, q, k] or [q, k]")
    txt_tokens = mask.shape[1] - (hi * wi)
    txt_to_txt = mask[:, :txt_tokens, :txt_tokens]
    txt_to_img = mask[:, :txt_tokens, txt_tokens:]
    img_to_img = mask[:, txt_tokens:, txt_tokens:]
    img_to_txt = mask[:, txt_tokens:, :txt_tokens]
    txt_to_img = rearrange  (txt_to_img, "b t (h w) -> b t h w", h=hi, w=wi)
    txt_to_img = interpolate(txt_to_img, size=img_size_out, mode="bilinear")
    txt_to_img = rearrange  (txt_to_img, "b t h w -> b t (h w)")
    img_to_img = rearrange  (img_to_img, "b hw (h w) -> b hw h w", h=hi, w=wi)
    img_to_img = interpolate(img_to_img, size=img_size_out, mode="bilinear")
    img_to_img = rearrange  (img_to_img, "b (hk wk) hq wq -> b (hq wq) hk wk", hk=hi, wk=wi)
    img_to_img = interpolate(img_to_img, size=img_size_out, mode="bilinear")
    img_to_img = rearrange  (img_to_img, "b (hq wq) hk wk -> b (hk wk) (hq wq)", hq=ho, wq=wo)
    img_to_txt = rearrange  (img_to_txt, "b (h w) t -> b t h w", h=hi, w=wi)
    img_to_txt = interpolate(img_to_txt, size=img_size_out, mode="bilinear")
    img_to_txt = rearrange  (img_to_txt, "b t h w -> b (h w) t")
    out = torch.cat([
        torch.cat([txt_to_txt, txt_to_img], dim=2),
        torch.cat([img_to_txt, img_to_img], dim=2)],
        dim=1
    )
    return out 