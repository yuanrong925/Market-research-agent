"""Market Research Agent — FastAPI 应用入口

启动方式: uvicorn app:app --host 0.0.0.0 --port 8000 --reload
"""

# ⚠️ 必须在所有 import 之前加载 .env，否则 core/config.py 等模块
# 在导入时会用 os.getenv 读取默认值（localhost:11434），导致 .env 配置失效
from dotenv import load_dotenv
load_dotenv(override=True)

import uvicorn
from business.market_research.api import app

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )