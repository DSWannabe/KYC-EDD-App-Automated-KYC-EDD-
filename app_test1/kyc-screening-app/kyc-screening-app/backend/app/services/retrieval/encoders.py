"""Encoder (bge-m3) và reranker (bge-reranker-v2-m3). Mỗi cái nạp một lần rồi dùng lại.

KYC_ENCODER_MODE=real: model thật (GPU nếu có, không thì CPU).
KYC_ENCODER_MODE=mock: bản giả bằng băm từ, chỉ để kiểm tra luồng chạy.
"""
import os
import threading
import zlib

import numpy as np

from app import config
from app.services.common import ham_chung as hc

MODEL_ENCODER = "BAAI/bge-m3"
MODEL_RERANK = "BAAI/bge-reranker-v2-m3"
SO_CHIEU = 1024   # số chiều của bge-m3

_khoa = threading.Lock()
_da_nap = {}


# ---------- Bản thật ----------

def _thiet_bi():
    import torch
    return "cuda" if torch.cuda.is_available() else "cpu"


class BgeM3:
    def __init__(self):
        os.environ["USE_TF"] = "0"   # tránh transformers tải TensorFlow
        from sentence_transformers import SentenceTransformer
        thiet_bi = _thiet_bi()
        self.model = SentenceTransformer(MODEL_ENCODER, device=thiet_bi)
        if thiet_bi == "cuda":
            self.model.half()
        self.model.max_seq_length = 512

    def encode(self, texts, batch_size=16):
        vec = self.model.encode(list(texts), batch_size=batch_size, normalize_embeddings=True)
        return np.asarray(vec, dtype=np.float32)


class BgeReranker:
    def __init__(self):
        os.environ["USE_TF"] = "0"
        from sentence_transformers import CrossEncoder
        thiet_bi = _thiet_bi()
        self.model = CrossEncoder(MODEL_RERANK, max_length=512, device=thiet_bi)
        if thiet_bi == "cuda":
            self.model.model.half()

    def predict(self, cap_van_ban, batch_size=8):
        return [float(s) for s in self.model.predict(cap_van_ban, batch_size=batch_size)]


# ---------- Bản giả ----------

class MockEncoder:
    """Mỗi từ băm vào một chiều của vector, rồi chuẩn hóa. Hai văn bản chung từ thì giống nhau."""

    def encode(self, texts, batch_size=16):
        out = np.zeros((len(texts), SO_CHIEU), dtype=np.float32)
        for i, text in enumerate(texts):
            for tu in hc.tach_tu(text):
                out[i, zlib.crc32(tu.encode("utf-8")) % SO_CHIEU] += 1.0
            norm = np.linalg.norm(out[i])
            if norm > 0:
                out[i] /= norm
        return out


class MockReranker:
    """Điểm = số từ rủi ro có trong bài, nén về khoảng 0 đến 1."""

    def __init__(self):
        self.tu_rui_ro = set(hc.cum_tu_thanh_token(hc.CUM_TU_RUI_RO))

    def predict(self, cap_van_ban, batch_size=8):
        diem = []
        for _, van_ban in cap_van_ban:
            dem = len(self.tu_rui_ro & set(hc.tach_tu_bigram(van_ban)))
            diem.append(dem / (dem + 5))
        return diem


# ---------- Lấy dùng chung ----------

def _lay(ten, tao_that, tao_gia):
    with _khoa:
        if ten not in _da_nap:
            _da_nap[ten] = tao_gia() if config.ENCODER_MODE == "mock" else tao_that()
        return _da_nap[ten]


def lay_encoder():
    return _lay("encoder", BgeM3, MockEncoder)


def lay_reranker():
    return _lay("reranker", BgeReranker, MockReranker)
