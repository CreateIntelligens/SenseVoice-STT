# SenseVoice API Docker 部署

這是一個容器化的 SenseVoice 語音識別 API 服務，支援多語言語音識別、情感識別、音頻事件檢測，並自動將簡體中文轉換為繁體中文。

## 功能特色

- 🎯 **多語言語音識別**: 支援中文、英文、粵語、日語、韓語
- 😊 **情感識別**: 識別語音中的情感（開心、生氣、悲傷等）
- 🎵 **音頻事件檢測**: 檢測背景音樂、掌聲、笑聲等
- 🔄 **簡繁轉換**: 自動將識別結果轉換為繁體中文
- 💾 **記憶體管理**: 智能 GPU 記憶體管理和監控
- 🐳 **容器化部署**: 支援 Docker 和 GPU 加速

## 快速開始

### 1. 克隆專案

```bash
# 克隆專案
git clone <your-repository-url>
cd sensevoice_api

# 或者下載並解壓縮專案文件
```

### 2. 環境配置（可選）

```bash
# 複製環境變數範例文件
cp .env.example .env

# 根據需要編輯環境變數
nano .env
```

### 3. 構建並啟動服務

```bash
# 使用 Docker Compose 構建並啟動
docker-compose up --build

# 背景運行
docker-compose up -d --build
```

### 2. 首次運行（模型下載）

首次啟動時，如果 `models/` 目錄為空，系統會自動從 ModelScope 下載模型：

```bash
# 查看日誌
docker-compose logs -f sensevoice-api
```

你會看到類似的輸出：
```
本地模型不存在，將從 ModelScope 下載...
正在載入模型: iic/SenseVoiceSmall
Downloading Model from https://www.modelscope.cn...
```

### 3. 後續運行（使用本地模型）

下載完成後，可以將模型複製到本地目錄以加快後續啟動：

```bash
# 進入容器
docker-compose exec sensevoice-api bash

# 複製模型到本地目錄
cp -r ~/.cache/modelscope/hub/iic/SenseVoiceSmall ./models/iic/

# 退出容器
exit

# 重啟服務（現在會使用本地模型）
docker-compose restart
```

## API 使用

### `/api/v1/asr` 語音識別 API

#### 端點資訊
- **URL**: `POST /api/v1/asr`
- **Content-Type**: `multipart/form-data`
- **功能**: 將音頻文件轉換為文字，支援多語言、情感識別和音頻事件檢測

#### 請求參數

| 參數名 | 類型 | 必填 | 說明 |
|--------|------|------|------|
| `files` | File[] | ✅ | 音頻文件（支援 WAV、MP3 格式，建議 16KHz 採樣率） |
| `keys` | String | ✅ | 文件標識符，多個文件用逗號分隔 |
| `lang` | String | ❌ | 語言設定，預設為 `auto` |

#### 支援的語言選項
- `auto`: 自動檢測（預設）
- `zh`: 中文（普通話）
- `en`: 英文
- `yue`: 粵語
- `ja`: 日語
- `ko`: 韓語
- `nospeech`: 無語音

### 請求範例

#### 1. 基本單文件識別

```bash
curl -X POST "http://localhost:50002/api/v1/asr" \
  -F "files=@audio.wav" \
  -F "keys=my_audio" \
  -F "lang=auto"
```

#### 2. 多文件批次處理

```bash
curl -X POST "http://localhost:50002/api/v1/asr" \
  -F "files=@audio1.wav" \
  -F "files=@audio2.mp3" \
  -F "keys=audio1,audio2" \
  -F "lang=zh"
```

#### 3. 指定語言識別

```bash
# 中文識別
curl -X POST "http://localhost:50002/api/v1/asr" \
  -F "files=@chinese_audio.wav" \
  -F "keys=chinese_test" \
  -F "lang=zh"

# 英文識別
curl -X POST "http://localhost:50002/api/v1/asr" \
  -F "files=@english_audio.wav" \
  -F "keys=english_test" \
  -F "lang=en"

# 粵語識別
curl -X POST "http://localhost:50002/api/v1/asr" \
  -F "files=@cantonese_audio.wav" \
  -F "keys=cantonese_test" \
  -F "lang=yue"
```

#### 4. Python 範例

```python
import requests

# 單文件上傳
def transcribe_audio(audio_file_path, key="audio", lang="auto"):
    url = "http://localhost:50002/api/v1/asr"
    
    with open(audio_file_path, 'rb') as f:
        files = {'files': f}
        data = {
            'keys': key,
            'lang': lang
        }
        response = requests.post(url, files=files, data=data)
    
    return response.json()

# 使用範例
result = transcribe_audio("test_audio.wav", "test", "zh")
print(result)

# 多文件上傳
def transcribe_multiple_audios(audio_files, keys, lang="auto"):
    url = "http://localhost:50002/api/v1/asr"
    
    files = [('files', open(f, 'rb')) for f in audio_files]
    data = {
        'keys': ','.join(keys),
        'lang': lang
    }
    
    try:
        response = requests.post(url, files=files, data=data)
        return response.json()
    finally:
        # 關閉文件
        for _, f in files:
            f.close()

# 使用範例
audio_files = ["audio1.wav", "audio2.wav"]
keys = ["audio1", "audio2"]
result = transcribe_multiple_audios(audio_files, keys, "auto")
print(result)
```

#### 5. JavaScript 範例

```javascript
// 單文件上傳
async function transcribeAudio(audioFile, key = "audio", lang = "auto") {
    const formData = new FormData();
    formData.append('files', audioFile);
    formData.append('keys', key);
    formData.append('lang', lang);
    
    const response = await fetch('http://localhost:50002/api/v1/asr', {
        method: 'POST',
        body: formData
    });
    
    return await response.json();
}

// 使用範例（在瀏覽器中）
const fileInput = document.getElementById('audioFile');
const file = fileInput.files[0];
transcribeAudio(file, 'test', 'zh').then(result => {
    console.log(result);
});

// 多文件上傳
async function transcribeMultipleAudios(audioFiles, keys, lang = "auto") {
    const formData = new FormData();
    
    audioFiles.forEach(file => {
        formData.append('files', file);
    });
    
    formData.append('keys', keys.join(','));
    formData.append('lang', lang);
    
    const response = await fetch('http://localhost:50002/api/v1/asr', {
        method: 'POST',
        body: formData
    });
    
    return await response.json();
}
```

### 回應格式

#### 成功回應結構

```json
{
  "result": [
    {
      "key": "audio_file_key",
      "text": "😊你好，這是一段測試音頻",
      "clean_text": "你好，這是一段測試音頻",
      "raw_text": "<|zh|><|HAPPY|><|Speech|>你好，這是一段測試音頻"
    }
  ]
}
```

#### 回應欄位說明

| 欄位名 | 類型 | 說明 |
|--------|------|------|
| `key` | String | 文件標識符（對應請求中的 keys） |
| `text` | String | **最終識別結果**（繁體中文，包含情感符號） |
| `clean_text` | String | **純文字結果**（繁體中文，移除所有標記） |
| `raw_text` | String | **原始識別結果**（包含語言、情感、事件標記） |

#### 詳細範例

##### 1. 中文語音（包含情感）

**請求**:
```bash
curl -X POST "http://localhost:50002/api/v1/asr" \
  -F "files=@happy_chinese.wav" \
  -F "keys=happy_test" \
  -F "lang=zh"
```

**回應**:
```json
{
  "result": [
    {
      "key": "happy_test",
      "text": "😊今天天氣真好，我很開心！",
      "clean_text": "今天天氣真好，我很開心！",
      "raw_text": "<|zh|><|HAPPY|><|Speech|>今天天气真好，我很开心！"
    }
  ]
}
```

##### 2. 英文語音

**請求**:
```bash
curl -X POST "http://localhost:50002/api/v1/asr" \
  -F "files=@english_audio.wav" \
  -F "keys=english_test" \
  -F "lang=en"
```

**回應**:
```json
{
  "result": [
    {
      "key": "english_test",
      "text": "Hello, this is a test audio file.",
      "clean_text": "Hello, this is a test audio file.",
      "raw_text": "<|en|><|NEUTRAL|><|Speech|>Hello, this is a test audio file."
    }
  ]
}
```

##### 3. 粵語語音

**請求**:
```bash
curl -X POST "http://localhost:50002/api/v1/asr" \
  -F "files=@cantonese_audio.wav" \
  -F "keys=cantonese_test" \
  -F "lang=yue"
```

**回應**:
```json
{
  "result": [
    {
      "key": "cantonese_test",
      "text": "你好，我係香港人。",
      "clean_text": "你好，我係香港人。",
      "raw_text": "<|yue|><|NEUTRAL|><|Speech|>你好，我系香港人。"
    }
  ]
}
```

##### 4. 包含背景音樂的語音

**回應**:
```json
{
  "result": [
    {
      "key": "music_test",
      "text": "🎵😊這首歌很好聽",
      "clean_text": "這首歌很好聽",
      "raw_text": "<|zh|><|HAPPY|><|Music|><|Speech|>这首歌很好听"
    }
  ]
}
```

##### 5. 多文件批次處理

**請求**:
```bash
curl -X POST "http://localhost:50002/api/v1/asr" \
  -F "files=@audio1.wav" \
  -F "files=@audio2.wav" \
  -F "keys=file1,file2" \
  -F "lang=auto"
```

**回應**:
```json
{
  "result": [
    {
      "key": "file1",
      "text": "😊你好世界",
      "clean_text": "你好世界",
      "raw_text": "<|zh|><|HAPPY|><|Speech|>你好世界"
    },
    {
      "key": "file2",
      "text": "Hello world",
      "clean_text": "Hello world",
      "raw_text": "<|en|><|NEUTRAL|><|Speech|>Hello world"
    }
  ]
}
```

#### 情感標記說明

| 情感標記 | 符號 | 說明 |
|----------|------|------|
| `<|HAPPY|>` | 😊 | 開心、愉悅 |
| `<|SAD|>` | 😢 | 悲傷、難過 |
| `<|ANGRY|>` | 😠 | 生氣、憤怒 |
| `<|NEUTRAL|>` | - | 中性情感 |
| `<|SURPRISE|>` | 😲 | 驚訝 |

#### 音頻事件標記說明

| 事件標記 | 符號 | 說明 |
|----------|------|------|
| `<|Speech|>` | - | 語音內容 |
| `<|Music|>` | 🎵 | 背景音樂 |
| `<|Applause|>` | 👏 | 掌聲 |
| `<|Laughter|>` | 😄 | 笑聲 |

#### 錯誤回應

```json
{
  "detail": "錯誤描述"
}
```

常見錯誤：
- `422 Unprocessable Entity`: 請求參數錯誤
- `500 Internal Server Error`: 服務器內部錯誤

### 記憶體監控 API

#### 查看 GPU 記憶體狀態

```bash
curl http://localhost:50002/memory
```

**回應範例**:
```json
{
  "gpu_available": true,
  "allocated_gb": 2.15,
  "cached_gb": 2.50,
  "total_gb": 8.00,
  "usage_percent": 26.88,
  "device_name": "NVIDIA GeForce RTX 3080"
}
```

#### 手動清理 GPU 記憶體

```bash
curl -X POST http://localhost:50002/memory/cleanup
```

**回應範例**:
```json
{
  "cleanup_performed": true,
  "before": {
    "allocated_gb": 2.15,
    "cached_gb": 2.50
  },
  "after": {
    "allocated_gb": 2.15,
    "cached_gb": 2.15
  },
  "freed_cache_gb": 0.35
}
```

### API 文檔

訪問 http://localhost:50002/docs 查看完整的 Swagger API 文檔。

## 目錄結構

```
sensevoice_api/
├── api.py                    # API 主程式
├── model.py                  # SenseVoice 模型定義
├── requirements.txt          # Python 依賴
├── Dockerfile               # Docker 映像檔
├── docker-compose.yaml      # Docker Compose 配置
├── README.md                # 說明文檔
├── models/                  # 模型存放目錄
│   └── iic/
│       └── SenseVoiceSmall/ # 下載的模型文件
└── utils/                   # 工具模組
    ├── __init__.py
    ├── frontend.py
    ├── infer_utils.py
    └── model_bin.py
```

## 環境變數

- `SENSEVOICE_DEVICE`: GPU 設備設定（預設: cuda:0）
- `CUDA_VISIBLE_DEVICES`: 可見的 GPU 設備（預設: 0）

## 開發模式

由於使用了 Volume 掛載，你可以直接修改代碼，容器會自動重載：

```bash
# 修改 api.py 後，重啟服務
docker-compose restart sensevoice-api
```

## 故障排除

### GPU 支援問題

確保系統已安裝 NVIDIA Docker 支援：

```bash
# 安裝 nvidia-docker2
sudo apt-get install nvidia-docker2
sudo systemctl restart docker
```

### 記憶體不足

如果遇到 GPU 記憶體不足，可以：

1. 使用記憶體清理 API: `POST /memory/cleanup`
2. 重啟容器: `docker-compose restart`
3. 調整批次大小或使用 CPU 模式

### 模型下載失敗

如果模型下載失敗，可以手動下載：

```bash
# 進入容器
docker-compose exec sensevoice-api bash

# 手動觸發下載
python3 -c "
from funasr import AutoModel
model = AutoModel(model='iic/SenseVoiceSmall', device='cpu')
"
```

## Git 使用說明

### 初始化 Git 倉庫

```bash
# 進入專案目錄
cd sensevoice_api

# 初始化 Git 倉庫
git init

# 設置主分支
git branch -M main

# 添加所有文件
git add .

# 首次提交
git commit -m "Initial commit: SenseVoice API"

# 連接遠程倉庫
git remote add origin <your-repository-url>

# 推送到遠程倉庫
git push -u origin main
```

### 常用 Git 操作

```bash
# 查看狀態
git status

# 添加修改的文件
git add .

# 提交變更
git commit -m "描述你的變更"

# 推送到遠程倉庫
git push

# 拉取最新變更
git pull
```

## 版本資訊

### v1.0.0 功能特色

- 🎯 多語言語音識別（中文、英文、粵語、日語、韓語）
- 😊 情感識別（開心、生氣、悲傷、驚訝、中性）
- 🎵 音頻事件檢測（背景音樂、掌聲、笑聲）
- 🔄 自動簡體轉繁體中文
- 💾 智能 GPU 記憶體管理和監控
- 🐳 完整的 Docker 容器化部署
- 📊 記憶體監控 API
- 📝 詳細的 API 文檔和使用範例

### 技術特性

- 基於 SenseVoice 模型的語音識別
- FastAPI 框架構建的 RESTful API
- 支援多文件批次處理
- 自動模型下載和本地快取
- Volume 掛載支援代碼熱更新
- Python 3.10 + PyTorch GPU 支援
- 智能模型路徑選擇（本地優先）

## 生產部署建議

1. **使用外部 Volume**: 將模型存放在外部 Volume 中
2. **負載均衡**: 使用 Nginx 或其他負載均衡器
3. **監控**: 添加 Prometheus 監控
4. **日誌**: 配置日誌收集和分析
5. **安全性**: 配置 HTTPS 和 API 認證
6. **備份**: 定期備份配置和日誌文件
