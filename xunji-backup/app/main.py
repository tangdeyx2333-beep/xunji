from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.endpoints import chat, upload, retrieval, history, auth, models
from app.db.session import init_db



# 初始化数据库
init_db()
# 1. 创建应用
app = FastAPI(title="知微 (ZhiWei) RAG API")

# 2. 配置跨域 (CORS) - 这一步对前后端分离非常重要！
# 允许 Vue (通常是 localhost:5173 或 8080) 访问
origins = [
    "http://localhost:5173",  # Vue 默认端口
    "http://localhost:8080",
    "http://127.0.0.1:5173"
]
app.add_middleware(
    CORSMiddleware,
    # 允许的来源：允许前端地址，开发环境可以直接用 ["*"] 允许所有
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True, # 允许携带 Cookie/Token
    allow_methods=["*"],    # 允许所有方法 (GET, POST, PUT, DELETE...)
    allow_headers=["*"],    # 允许所有 Header (Authorization, Content-Type...)
)


# 3. 注册路由
# 把 chat.py 里的路由挂载到 /api 路径下
app.include_router(chat.router, prefix="/api", tags=["Chat"])
app.include_router(upload.router, prefix="/api", tags=["Upload/File"]) # Upload 里现在也有查询接口了
app.include_router(retrieval.router, prefix="/api", tags=["Retrieval/Debug"])
app.include_router(history.router, prefix="/api", tags=["History/Session"]) # 获取消息
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"]) # ★ 注册
app.include_router(models.router, prefix="/api", tags=["Models"]) # ★ 模型管理
# 4. 根路径测试
@app.get("/")
def root():
    return {"message": "知微后端服务已启动 🚀"}

# 5. 启动代码 (仅在直接运行此文件时执行)
if __name__ == "__main__":
    import uvicorn
    # 对应 Java 的 SpringApplication.run()
    uvicorn.run(app, host="127.0.0.1", port=8080)