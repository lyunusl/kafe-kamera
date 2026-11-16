"""(kafe-kamera-gpu/kafe_gpu/pose.py kopyası.) YOLO11-pose pre/post-processing in plain NumPy + OpenCV, identical to ultralytics 8.4.208 predict/track.

Reference (ultralytics, PyTorch .pt model, rect=True):
  LetterBox(imgsz, auto=True, stride=32): r = min(imgsz/h, imgsz/w); new_unpad = round(w*r), round(h*r);
  pad = (imgsz - new) % 32, split in two (top = round(dh/2 - 0.1), bottom = round(dh/2 + 0.1)); cv2.resize INTER_LINEAR;
  border value 114; BGR -> RGB; float /255; NCHW.
  NMS: candidates conf > conf_thres, xywh -> xyxy, greedy IoU NMS (suppress IoU > iou_thres), max_det 300,
  max_nms 30000; nc = 1 so class offset is 0.
  Boxes: subtract pad, divide by gain, clip to frame. Keypoints: same, clipped (scale_coords + clip_coords).
Model output: (B, 4 + 1 + 17*3, N) = xywh, person score, 17 x (x, y, visibility probability).
"""
from __future__ import annotations

import cv2
import numpy as np

STRIDE = 32
PAD_VALUE = 114
NKPT = 17
MAX_DET = 300
MAX_NMS = 30000


def letterbox_shape(h: int, w: int, imgsz: int, stride: int = STRIDE) -> dict:
    """Letterbox parameters for an (h, w) frame (auto/minimum-rectangle mode, like ultralytics with a .pt model)."""
    r = min(imgsz / h, imgsz / w)
    nw, nh = max(round(w * r), 1), max(round(h * r), 1)
    dw, dh = (imgsz - nw) % stride, (imgsz - nh) % stride
    dw, dh = dw / 2, dh / 2
    top, bottom = round(dh - 0.1), round(dh + 0.1)
    left, right = round(dw - 0.1), round(dw + 0.1)
    return {"new_unpad": (nw, nh), "top": top, "bottom": bottom, "left": left, "right": right,
            "in_h": nh + top + bottom, "in_w": nw + left + right, "orig": (h, w)}


def letterbox(img: np.ndarray, p: dict) -> np.ndarray:
    h, w = img.shape[:2]
    if (w, h) != p["new_unpad"]:
        img = cv2.resize(img, p["new_unpad"], interpolation=cv2.INTER_LINEAR)
    return cv2.copyMakeBorder(img, p["top"], p["bottom"], p["left"], p["right"], cv2.BORDER_CONSTANT,
                              value=(PAD_VALUE,) * 3)


def preprocess(frames: list[np.ndarray], imgsz: int, out: np.ndarray | None = None) -> tuple[np.ndarray, list[dict]]:
    """BGR uint8 frames (same letterboxed shape required for one batch) -> float32 NCHW RGB /255 and their params."""
    params = [letterbox_shape(f.shape[0], f.shape[1], imgsz) for f in frames]
    H, W = params[0]["in_h"], params[0]["in_w"]
    if any((p["in_h"], p["in_w"]) != (H, W) for p in params):
        raise ValueError("frames in one batch must letterbox to the same input shape")
    if out is None or out.shape != (len(frames), 3, H, W):
        out = np.empty((len(frames), 3, H, W), np.float32)
    for i, (f, p) in enumerate(zip(frames, params)):
        lb = letterbox(f, p)
        # BGR -> RGB and HWC -> CHW in one strided copy, then scale
        np.multiply(lb[:, :, ::-1].transpose(2, 0, 1), np.float32(1 / 255), out=out[i], casting="unsafe")
    return out, params


def _nms(boxes: np.ndarray, scores: np.ndarray, iou_thres: float) -> np.ndarray:
    """Greedy NMS (same rule as torchvision.ops.nms: drop boxes with IoU > iou_thres to a higher-scoring kept box).
    Ties are broken by original index (stable sort), like torchvision on CPU."""
    order = np.argsort(-scores, kind="stable")
    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    area = (x2 - x1) * (y2 - y1)
    keep = []
    while order.size:
        i = order[0]
        keep.append(i)
        if order.size == 1:
            break
        rest = order[1:]
        xx1 = np.maximum(x1[i], x1[rest])
        yy1 = np.maximum(y1[i], y1[rest])
        xx2 = np.minimum(x2[i], x2[rest])
        yy2 = np.minimum(y2[i], y2[rest])
        inter = np.clip(xx2 - xx1, 0, None) * np.clip(yy2 - yy1, 0, None)
        iou = inter / (area[i] + area[rest] - inter)
        order = rest[iou <= iou_thres]
    return np.asarray(keep, dtype=np.int64)


def postprocess(pred: np.ndarray, params: list[dict], conf: float, iou: float) -> list[tuple[np.ndarray, np.ndarray]]:
    """Raw output (B, 56, N) -> per image (dets (n, 6) = x1 y1 x2 y2 conf cls in frame pixels, kpts (n, 17, 3))."""
    pred = np.asarray(pred, dtype=np.float32)
    out = []
    for b, p in enumerate(params):
        x = pred[b]
        sc = x[4]
        sel = np.nonzero(sc > conf)[0]
        if sel.size == 0:
            out.append((np.zeros((0, 6), np.float32), np.zeros((0, NKPT, 3), np.float32)))
            continue
        x = x[:, sel].T  # (n, 56)
        if x.shape[0] > MAX_NMS:
            x = x[np.argsort(-x[:, 4], kind="stable")[:MAX_NMS]]
        xy, wh = x[:, 0:2], x[:, 2:4] / 2
        boxes = np.concatenate([xy - wh, xy + wh], 1)
        keep = _nms(boxes, x[:, 4], iou)[:MAX_DET]
        boxes, scores, k = boxes[keep], x[keep, 4], x[keep, 5:].reshape(-1, NKPT, 3).copy()
        h0, w0 = p["orig"]
        gx, gy = p["new_unpad"][0] / w0, p["new_unpad"][1] / h0
        boxes[:, [0, 2]] = ((boxes[:, [0, 2]] - p["left"]) / gx).clip(0, w0)
        boxes[:, [1, 3]] = ((boxes[:, [1, 3]] - p["top"]) / gy).clip(0, h0)
        k[..., 0] = ((k[..., 0] - p["left"]) / gx).clip(0, w0)
        k[..., 1] = ((k[..., 1] - p["top"]) / gy).clip(0, h0)
        dets = np.concatenate([boxes, scores[:, None], np.zeros((len(keep), 1), np.float32)], 1).astype(np.float32)
        out.append((dets, k.astype(np.float32)))
    return out
