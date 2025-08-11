# 使用 Python 3.10 slim 基礎映像
FROM python:3.10-slim

# 設定環境變數
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV CUDA_VISIBLE_DEVICES=0

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    git \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# 設定工作目錄
WORKDIR /app

# 複製 requirements.txt
COPY requirements.txt .

# 安裝 PyTorch（GPU 版本）
RUN pip3 install torch torchaudio --index-url https://download.pytorch.org/whl/cu118

# 安裝其他 Python 依賴
RUN pip3 install --no-cache-dir -r requirements.txt

# 複製應用程式代碼
COPY . .

# 創建模型目錄
RUN mkdir -p /app/models

# 暴露端口
EXPOSE 50002

# 設定環境變數
ENV SENSEVOICE_DEVICE=cuda:0
ENV PYTHONPATH=/app

# 啟動命令
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "50002"]
