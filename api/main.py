"""FastAPI 入口。

POST /api/exposure 校验并计算噪声暴露结论；
任何字段缺失、额外频带/字段、非法数值均由 Pydantic 返回 422。
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .schemas import ExposureIn, ExposureOut
from .service import compute_exposure

app = FastAPI(title="车间噪声暴露工作台", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/exposure", response_model=ExposureOut)
def exposure(payload: ExposureIn) -> ExposureOut:
    return compute_exposure(payload)
