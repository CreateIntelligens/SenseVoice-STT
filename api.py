# Set the device with environment, default is cuda:0
# export SENSEVOICE_DEVICE=cuda:1

import os, re, gc
import torch
import contextlib
import opencc
from fastapi import FastAPI, File, Form
from fastapi.responses import HTMLResponse
from typing_extensions import Annotated
from typing import List
from enum import Enum
import torchaudio
from model import SenseVoiceSmall
from funasr.utils.postprocess_utils import rich_transcription_postprocess
from io import BytesIO

# 設定 ModelScope 快取目錄到當前目錄，這樣模型會下載到 ./models/iic/SenseVoiceSmall
os.environ['MODELSCOPE_CACHE'] = '.'

class Language(str, Enum):
    auto = "auto"
    zh = "zh"
    en = "en"
    yue = "yue"
    ja = "ja"
    ko = "ko"
    nospeech = "nospeech"

def verify_model_integrity(model_path):
    """驗證模型文件完整性"""
    if not os.path.exists(model_path):
        return False
    
    files = os.listdir(model_path)
    # 檢查是否有基本的模型文件
    has_config = any('config' in f.lower() for f in files)
    has_model = any(f.endswith(('.pt', '.pth', '.bin')) for f in files)
    
    return has_config and has_model and len(files) > 2

def get_model_path():
    """智能選擇模型路徑"""
    local_model_path = "./models/iic/SenseVoiceSmall"
    
    # 檢查本地模型是否存在且完整
    if verify_model_integrity(local_model_path):
        print(f"使用本地模型: {local_model_path}")
        return local_model_path
    else:
        print("本地模型不存在或不完整，將下載到 ./models/ 目錄...")
        # 確保 models 目錄存在
        os.makedirs("./models", exist_ok=True)
        return "iic/SenseVoiceSmall"

# 智能選擇模型路徑
model_dir = get_model_path()
print(f"正在載入模型: {model_dir}")
m, kwargs = SenseVoiceSmall.from_pretrained(model=model_dir, device=os.getenv("SENSEVOICE_DEVICE", "cuda:0"))
m.eval()

regex = r"<\|.*\|>"

# 初始化簡體轉繁體轉換器
converter = opencc.OpenCC('s2t')

app = FastAPI()

def convert_to_traditional(text: str) -> str:
    """將簡體中文轉換為繁體中文"""
    try:
        return converter.convert(text)
    except Exception as e:
        print(f"簡繁轉換錯誤: {e}")
        return text  # 如果轉換失敗，返回原文

def log_gpu_memory(stage: str):
    """記錄 GPU 記憶體使用情況"""
    if torch.cuda.is_available():
        allocated = torch.cuda.memory_allocated() / 1024**3
        cached = torch.cuda.memory_reserved() / 1024**3
        print(f"[{stage}] GPU 記憶體 - 已分配: {allocated:.2f}GB, 快取: {cached:.2f}GB")

@contextlib.contextmanager
def gpu_memory_cleanup():
    """GPU 記憶體清理上下文管理器"""
    try:
        yield
    finally:
        # 強制清理 GPU 快取
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        # 強制垃圾回收
        gc.collect()


@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <!DOCTYPE html>
    <html>
        <head>
            <meta charset=utf-8>
            <title>Api information</title>
        </head>
        <body>
            <a href='./docs'>Documents of API</a><br>
            <a href='./memory'>Check GPU Memory Usage</a>
        </body>
    </html>
    """

@app.get("/memory")
async def get_memory_status():
    """獲取當前 GPU 記憶體使用狀態"""
    if torch.cuda.is_available():
        allocated = torch.cuda.memory_allocated() / 1024**3
        cached = torch.cuda.memory_reserved() / 1024**3
        total = torch.cuda.get_device_properties(0).total_memory / 1024**3
        
        return {
            "gpu_available": True,
            "allocated_gb": round(allocated, 2),
            "cached_gb": round(cached, 2),
            "total_gb": round(total, 2),
            "usage_percent": round((allocated / total) * 100, 2),
            "device_name": torch.cuda.get_device_name(0)
        }
    else:
        return {
            "gpu_available": False,
            "message": "CUDA not available"
        }

@app.post("/memory/cleanup")
async def manual_cleanup():
    """手動清理 GPU 記憶體"""
    if torch.cuda.is_available():
        before_allocated = torch.cuda.memory_allocated() / 1024**3
        before_cached = torch.cuda.memory_reserved() / 1024**3
        
        torch.cuda.empty_cache()
        gc.collect()
        
        after_allocated = torch.cuda.memory_allocated() / 1024**3
        after_cached = torch.cuda.memory_reserved() / 1024**3
        
        return {
            "cleanup_performed": True,
            "before": {
                "allocated_gb": round(before_allocated, 2),
                "cached_gb": round(before_cached, 2)
            },
            "after": {
                "allocated_gb": round(after_allocated, 2),
                "cached_gb": round(after_cached, 2)
            },
            "freed_cache_gb": round(before_cached - after_cached, 2)
        }
    else:
        return {
            "cleanup_performed": False,
            "message": "CUDA not available"
        }

@app.post("/api/v1/asr")
async def turn_audio_to_text(files: Annotated[List[bytes], File(description="wav or mp3 audios in 16KHz")], keys: Annotated[str, Form(description="name of each audio joined with comma")], lang: Annotated[Language, Form(description="language of audio content")] = "auto"):
    # 記錄開始時的記憶體狀態
    log_gpu_memory("API 請求開始")
    
    with gpu_memory_cleanup():
        try:
            audios = []
            audio_fs = 0
            
            # 處理音頻文件
            for file in files:
                file_io = BytesIO(file)
                data_or_path_or_list, audio_fs = torchaudio.load(file_io)
                data_or_path_or_list = data_or_path_or_list.mean(0)
                audios.append(data_or_path_or_list)
                file_io.close()
            
            log_gpu_memory("音頻載入完成")
            
            # 處理參數
            if lang == "":
                lang = "auto"
            if keys == "":
                key = ["wav_file_tmp_name"]
            else:
                key = keys.split(",")
            
            # 使用 no_grad 進行推理以節省記憶體
            with torch.no_grad():
                res = m.inference(
                    data_in=audios,
                    language=lang, # "zh", "en", "yue", "ja", "ko", "nospeech"
                    use_itn=True,
                    ban_emo_unk=False,
                    key=key,
                    fs=audio_fs,
                    **kwargs,
                )
            
            log_gpu_memory("推理完成")
            
            # 處理結果
            if len(res) == 0:
                return {"result": []}
            
            for it in res[0]:
                # 保存原始文字
                it["raw_text"] = convert_to_traditional(it["text"])
                
                # 處理清理後的文字（移除標記）
                clean_text = re.sub(regex, "", it["text"], 0, re.MULTILINE)
                it["clean_text"] = convert_to_traditional(clean_text)
                
                # 處理完整的文字（包含情感符號等）
                processed_text = rich_transcription_postprocess(it["text"])
                it["text"] = convert_to_traditional(processed_text)
            
            result = {"result": res[0]}
            
            # 手動清理大型變數
            del audios
            del res
            
            log_gpu_memory("處理完成，準備清理")
            
            return result
            
        except Exception as e:
            log_gpu_memory("發生錯誤")
            print(f"API 錯誤: {str(e)}")
            raise e
