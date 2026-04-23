"""启动脚本"""
#v1 基于hello-agent框架下的入口文件，现在已经废弃，最终版本要删掉这个文件
import uvicorn
from app.config import get_settings

if __name__ == "__main__":
    settings = get_settings()
    
    uvicorn.run(
        "app.api.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_level=settings.log_level.lower()
    )

