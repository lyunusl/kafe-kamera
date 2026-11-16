"""(kafe-kamera-gpu/kafe_gpu/tracker.py kopyası.) ByteTrack on plain NumPy detections, reusing ultralytics' own BYTETracker (CPU only; torch is imported by ultralytics
but no CUDA build is needed).

Reproduces ultralytics.trackers.track.on_predict_postprocess_end for one stream:
  tracks = tracker.update(Boxes(dets), frame)
  no tracks -> if any tracked strack is not activated the result is emptied, else the raw detections stay (no ids);
  otherwise the result is result[idx] with boxes replaced by the tracker's (Kalman) boxes, keypoints from the detection.

One BYTETracker per camera. ultralytics keeps the id counter in a class attribute shared by every tracker in the
process (BaseTrack._count, reset by each new tracker); this wrapper swaps a per-camera counter in and out around each
update so several cameras in one process keep independent, never-reused ids (1, 2, 3 ... per camera, like today's
one-process-per-camera engine)."""
from __future__ import annotations

import os
import types

import numpy as np

DEFAULT_CFG = {"tracker_type": "bytetrack", "track_high_thresh": 0.25, "track_low_thresh": 0.1,
               "new_track_thresh": 0.25, "track_buffer": 30, "match_thresh": 0.8, "fuse_score": True}


def load_cfg(path: str | None) -> dict:
    """bytetrack.yaml (ultralytics default) or a file written by blok.izci_dosyasi()."""
    cfg = dict(DEFAULT_CFG)
    if path and os.path.basename(path) != "bytetrack.yaml" and os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                k, _, v = line.partition(":")
                k, v = k.strip(), v.split("#")[0].strip()
                if not k or not v:
                    continue
                if v in ("True", "False"):
                    cfg[k] = v == "True"
                else:
                    try:
                        cfg[k] = int(v)
                    except ValueError:
                        try:
                            cfg[k] = float(v)
                        except ValueError:
                            cfg[k] = v
    return cfg


class StreamTracker:
    def __init__(self, cfg: dict | str | None = None):
        from ultralytics.trackers.basetrack import BaseTrack
        from ultralytics.trackers.byte_tracker import BYTETracker

        if not isinstance(cfg, dict):
            cfg = load_cfg(cfg)
        self._base = BaseTrack
        saved = BaseTrack._count
        self.tracker = BYTETracker(args=types.SimpleNamespace(**cfg))  # resets the shared counter
        BaseTrack._count = saved
        self._count = 0

    def update(self, frame: np.ndarray, dets: np.ndarray, kpts: np.ndarray):
        """dets (n, 6) x1 y1 x2 y2 conf cls, kpts (n, 17, 3) in frame pixels.
        Returns (boxes (m, 4), ids (m,) or None, kpts (m, 17, 3)) exactly like ultralytics' Results after tracking."""
        from ultralytics.engine.results import Boxes

        boxes = Boxes(dets, frame.shape[:2])
        saved, self._base._count = self._base._count, self._count
        try:
            tracks = self.tracker.update(boxes, frame)
        finally:
            self._count, self._base._count = self._base._count, saved
        if len(tracks) == 0:
            if any(not t.is_activated for t in self.tracker.tracked_stracks):
                return np.zeros((0, 4), np.float32), None, np.zeros((0, 17, 3), np.float32)
            return dets[:, :4], None, kpts
        idx = tracks[:, -1].astype(int)
        return tracks[:, :4].astype(np.float32), tracks[:, 4].astype(int), kpts[idx]
