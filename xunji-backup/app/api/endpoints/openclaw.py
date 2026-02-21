import asyncio
import json
import os
from urllib.parse import urlparse
from typing import AsyncGenerator, Dict, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from starlette.concurrency import iterate_in_threadpool
from pydantic import BaseModel, model_validator
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.sql_models import OpenClawConfig as OpenClawConfigModel
from app.schemas.openclaw import OpenClawConfig as OpenClawConfigSchema, OpenClawConfigCreate, OpenClawConfigUpdate


# 尝试引入 OpenClaw 适配器与配置
try:
    from openclaw_webchat_adapter.ws_adapter import OpenClawChatWsAdapter
    from openclaw_webchat_adapter.config import AdapterSettings
except ImportError:
    OpenClawChatWsAdapter = None
    AdapterSettings = None

# 尝试引入 SSHTunnel
try:
    import paramiko
    # 修复 Paramiko 3.x/4.x 移除 DSSKey 导致 sshtunnel 报错的问题
    if not hasattr(paramiko, 'DSSKey'):
        paramiko.DSSKey = paramiko.PKey  # 简单 Mock 一个属性，防止 sshtunnel 导入失败
    from sshtunnel import SSHTunnelForwarder
except ImportError:
    SSHTunnelForwarder = None

router = APIRouter()

# --- 全局内存存储 ---
# config_id -> Adapter 实例
active_connections: Dict[str, "OpenClawChatWsAdapter"] = {}
# config_id -> SSH Tunnel 实例
active_tunnels: Dict[str, "SSHTunnelForwarder"] = {}


# --- 请求模型 ---

class OpenClawConnectRequest(BaseModel):
    user_id: str
    display_name: str
    gateway_url: str
    gateway_token: Optional[str] = None
    gateway_password: Optional[str] = None
    session_key: str

    use_ssh: bool = False
    ssh_host: Optional[str] = None
    ssh_port: int = 22
    ssh_user: Optional[str] = None
    ssh_password: Optional[str] = None
    ssh_local_port: int = 0  # 0 表示随机端口

    @model_validator(mode='after')
    def check_auth(self):
        if not self.gateway_token and not self.gateway_password:
            raise ValueError('gateway_token 和 gateway_password 必须至少提供一个')
        if self.use_ssh:
            if not all([self.ssh_host, self.ssh_user, self.ssh_password]):
                raise ValueError('启用 SSH 时，必须提供 ssh_host, ssh_user, ssh_password')
            
            # 清洗 ssh_host：移除 http:// 或 https:// 前缀以及末尾的 /
            if self.ssh_host:
                host = self.ssh_host.strip()
                if '://' in host:
                    try:
                        parsed = urlparse(host)
                        host = parsed.hostname or host
                    except:
                        pass
                self.ssh_host = host.rstrip('/')
        return self


class OpenClawUpdateRequest(OpenClawConnectRequest):
    pass


class OpenClawConnectExistingRequest(BaseModel):
    config_id: str


class OpenClawChatRequest(BaseModel):
    config_id: str
    message: str


# --- 辅助函数 ---

@router.get("/configs", response_model=list[OpenClawConfigSchema])
async def get_openclaw_configs(user_id: str, db: Session = Depends(get_db)):
    """获取用户的所有 OpenClaw 配置"""
    configs = db.query(OpenClawConfigModel).filter(OpenClawConfigModel.user_id == user_id).all()
    return configs

@router.post("/configs", response_model=OpenClawConfigSchema)
async def create_openclaw_config(request: OpenClawConfigCreate, db: Session = Depends(get_db)):
    """创建新的 OpenClaw 配置"""
    db_config = OpenClawConfigModel(**request.model_dump())
    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    return db_config

@router.put("/configs/{config_id}", response_model=OpenClawConfigSchema)
async def update_openclaw_config(config_id: str, request: OpenClawConfigUpdate, db: Session = Depends(get_db)):
    """更新 OpenClaw 配置"""
    db_config = db.query(OpenClawConfigModel).filter(OpenClawConfigModel.id == config_id).first()
    if not db_config:
        raise HTTPException(status_code=404, detail="Config not found")
    
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_config, key, value)
    
    db_config.updated_at = datetime.now()
    db.commit()
    db.refresh(db_config)
    return db_config

@router.delete("/configs/{config_id}")
async def delete_openclaw_config(config_id: str, user_id: str, db: Session = Depends(get_db)):
    """删除 OpenClaw 配置"""
    db_config = db.query(OpenClawConfigModel).filter(OpenClawConfigModel.id == config_id, OpenClawConfigModel.user_id == user_id).first()
    if not db_config:
        raise HTTPException(status_code=404, detail="Config not found")
    
    db.delete(db_config)
    db.commit()
    return {"status": "deleted", "id": config_id}


def cleanup_connection(config_id: str):
    """清理指定配置的活跃连接和隧道"""
    if config_id in active_connections:
        try:
            adapter = active_connections[config_id]
            adapter.stop()
        except Exception as e:
            print(f"Error stopping adapter for config {config_id}: {e}")
        del active_connections[config_id]

    if config_id in active_tunnels:
        try:
            tunnel = active_tunnels[config_id]
            tunnel.stop()
        except Exception as e:
            print(f"Error stopping tunnel for config {config_id}: {e}")
        del active_tunnels[config_id]


def _create_adapter_settings(config: OpenClawConfigModel, override_url: Optional[str] = None) -> "AdapterSettings":
    """构造 OpenClaw AdapterSettings"""
    if AdapterSettings is None:
        raise RuntimeError("OpenClaw library not installed")
    
    return AdapterSettings(
        url=override_url or config.gateway_url,
        token=config.gateway_token,
        password=config.gateway_password,
        session_key=config.session_key
    )


@router.get("/history/{config_id}")
async def get_openclaw_history(config_id: str, db: Session = Depends(get_db)):
    """
    获取指定配置的 OpenClaw 历史聊天记录。

    该接口会根据 config_id 从数据库恢复 OpenClaw 连接，
    并从数据库中读取该配置的 session_key，用于获取对应的历史记录。

    Args:
        config_id (str): 配置唯一标识。
        db (Session): 数据库会话。

    Returns:
        List[Dict]: 符合前端格式要求的历史消息列表。
    """
    # 1. 从数据库获取配置以取得 session_key
    config = db.query(OpenClawConfigModel).filter(OpenClawConfigModel.id == config_id).first()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到 OpenClaw 配置，请先进行连接配置。"
        )
    
    session_key = config.session_key

    # 2. 获取或恢复适配器连接
    adapter = await _get_adapter_for_config(config_id, db)
    if not adapter:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无法建立 OpenClaw 连接，请检查配置信息。"
        )

    try:
        # 3. 使用数据库中的 session_key 调用适配器获取历史记录
        # 适配器内部会根据 session_key 定位到具体的对话会话
        history = adapter.get_chat_history_simple(session_key)
        
        # history 的格式应为：
        # [
        #   {
        #     "role": "user",
        #     "content": [{"type": "text", "text": "..."}],
        #     "timestamp": ...
        #   },
        #   ...
        # ]
        return history
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取 OpenClaw 历史记录失败: {str(e)}"
        )


# --- 接口实现 ---

@router.post("/connect")
async def connect_openclaw(request: OpenClawConnectExistingRequest, db: Session = Depends(get_db)):
    """
    通过 config_id 建立 OpenClaw 连接。
    """
    # 1. 查询配置
    config = db.query(OpenClawConfigModel).filter(OpenClawConfigModel.id == request.config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="未找到指定配置")
    
    # 2. 清理旧连接
    cleanup_connection(request.config_id)
    
    if OpenClawChatWsAdapter is None:
        raise HTTPException(status_code=500, detail="后端缺少 openclaw_webchat_adapter 依赖")

    tunnel = None
    final_gateway_url = config.gateway_url

    try:
        # 3. 建立 SSH 隧道 (如果需要)
        if config.use_ssh:
            if SSHTunnelForwarder is None:
                raise HTTPException(status_code=500, detail="后端缺少 sshtunnel 依赖，无法建立 SSH 隧道")

            try:
                # 解析网关 URL 获取目标端口
                parsed_url = urlparse(config.gateway_url)
                remote_host = parsed_url.hostname or "127.0.0.1"
                remote_port = parsed_url.port or 18789

                tunnel = SSHTunnelForwarder(
                    (config.ssh_host, config.ssh_port),
                    ssh_username=config.ssh_user,
                    ssh_password=config.ssh_password,
                    remote_bind_address=("127.0.0.1", remote_port),
                    local_bind_address=('127.0.0.1', config.ssh_local_port),
                    set_keepalive=30.0
                )
                tunnel.start()
                
                # 更新网关 URL 指向本地隧道端口
                local_port = tunnel.local_bind_port
                final_gateway_url = f"{parsed_url.scheme}://127.0.0.1:{local_port}{parsed_url.path}"
                print(f"SSH Tunnel established for config {request.config_id}: 127.0.0.1:{local_port} -> {config.ssh_host} -> 127.0.0.1:{remote_port}")
            
            except Exception as e:
                error_str = str(e)
                print(f"SSH Tunnel failed: {error_str}")
                
                # 针对常见配置错误给出更友好的提示
                if "SSH protocol banner" in error_str:
                    detail = f"SSH 建立失败：无法读取协议横幅。这通常是因为 SSH 端口 ({config.ssh_port}) 配置错误，该端口可能不是 SSH 服务（例如误填了网关端口）。请检查 SSH 端口是否应为 22。"
                elif "Connection refused" in error_str:
                    detail = f"SSH 建立失败：连接被拒绝。请检查 IP ({config.ssh_host}) 和端口 ({config.ssh_port}) 是否正确，以及防火墙是否放行。"
                elif "Authentication failed" in error_str:
                    detail = "SSH 建立失败：认证失败。请检查 SSH 用户名和密码是否正确。"
                else:
                    detail = f"SSH 隧道建立失败。错误: {error_str}"
                
                raise HTTPException(status_code=400, detail=detail)

        # 4. 建立 OpenClaw 连接
        try:
            settings = AdapterSettings(
                url=final_gateway_url,
                token=config.gateway_token,
                password=config.gateway_password,
                session_key=config.session_key
            )
            
            adapter = OpenClawChatWsAdapter.create_connected(settings=settings)
            
        except Exception as e:
            # 如果连接失败，且建立了隧道，需要关闭隧道
            if tunnel:
                tunnel.stop()
            
            error_msg = str(e)
            detail_msg = f"连接 OpenClaw 服务失败: {error_msg}。"
            if config.use_ssh:
                detail_msg += " SSH 隧道已建立，但 OpenClaw 握手失败。请确认远程服务器上的 OpenClaw 服务是否正常运行。"
            else:
                detail_msg += " 请检查 URL 是否连通或信息是否正确。"
                
            raise HTTPException(status_code=400, detail=detail_msg)

        # 5. 成功：缓存连接
        active_connections[request.config_id] = adapter
        if tunnel:
            active_tunnels[request.config_id] = tunnel

        return {"status": "connected", "config_id": request.config_id, "message": "OpenClaw 连接成功"}

    except HTTPException:
        raise
    except Exception as e:
        # 兜底异常处理
        if tunnel:
            tunnel.stop()
        cleanup_connection(request.config_id)
        raise HTTPException(status_code=500, detail=f"OpenClaw 连接过程中发生未知错误: {str(e)}")


async def _get_adapter_for_config(config_id: str, db: Session) -> Optional["OpenClawChatWsAdapter"]:
    """通过 config_id 获取 Adapter，如果内存没有则尝试从 DB 恢复"""
    
    # 1. 查内存
    if config_id in active_connections:
        return active_connections[config_id]

    # 2. 查数据库
    config = db.query(OpenClawConfigModel).filter(OpenClawConfigModel.id == config_id).first()
    if not config:
        return None

    print(f"Restoring OpenClaw connection for config {config_id} from database...")

    # 3. 尝试恢复连接 (复用 connect 逻辑的一部分，但简化)
    tunnel = None
    final_gateway_url = config.gateway_url

    try:
        if config.use_ssh:
            if SSHTunnelForwarder is None:
                print("Missing sshtunnel dependency during restore")
                return None
            
            parsed_url = urlparse(config.gateway_url)
            remote_host = parsed_url.hostname or "127.0.0.1"
            remote_port = parsed_url.port or 18789

            tunnel = SSHTunnelForwarder(
                (config.ssh_host, config.ssh_port),
                ssh_username=config.ssh_user,
                ssh_password=config.ssh_password,
                remote_bind_address=("127.0.0.1", remote_port),
                local_bind_address=('127.0.0.1', config.ssh_local_port),
                set_keepalive=30.0
            )
            tunnel.start()
            local_port = tunnel.local_bind_port
            final_gateway_url = f"{parsed_url.scheme}://127.0.0.1:{local_port}{parsed_url.path}"
        
        settings = AdapterSettings(
            url=final_gateway_url,
            token=config.gateway_token,
            password=config.gateway_password,
            session_key=config.session_key
        )
        adapter = OpenClawChatWsAdapter.create_connected(settings=settings)
        
        # 缓存
        active_connections[config_id] = adapter
        if tunnel:
            active_tunnels[config_id] = tunnel
        
        return adapter

    except Exception as e:
        print(f"Failed to restore connection for config {config_id}: {e}")
        if tunnel:
            try:
                tunnel.stop()
            except:
                pass
        return None
        if tunnel:
            active_tunnels[user_id] = tunnel
        
@router.post("/configs/connect", response_model=dict)
async def create_and_connect_openclaw(request: OpenClawConnectRequest, db: Session = Depends(get_db)):
    """
    创建新的 OpenClaw 配置并立即连接。
    """
    # 1. 创建配置
    db_config = OpenClawConfigModel(**request.model_dump())
    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    
    # 2. 立即连接
    connect_request = OpenClawConnectExistingRequest(config_id=db_config.id)
    return await connect_openclaw(connect_request, db)


async def openclaw_stream_generator(adapter: "OpenClawChatWsAdapter", message: str) -> AsyncGenerator[str, None]:
    """生成流式响应"""
    try:
        # 使用 iterate_in_threadpool 将同步生成器转换为异步迭代器
        # 这样可以防止同步生成器中的阻塞 IO 导致事件循环卡死
        sync_gen = adapter.stream_chat(message)
        async for char in iterate_in_threadpool(sync_gen):
            if char:
                # 打印日志以便调试
                # print(f"DEBUG: yielding char: {char}")
                yield f"data: {json.dumps({'content': char})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'content': f'OpenClaw 运行时错误: {str(e)}'})}\n\n"
    
    yield "data: [DONE]\n\n"


@router.post("/chat")
async def openclaw_chat(request: OpenClawChatRequest, db: Session = Depends(get_db)):
    """
    OpenClaw 对话接口。
    通过 config_id 定位连接配置。
    """
    # 1. 查询配置
    config = db.query(OpenClawConfigModel).filter(OpenClawConfigModel.id == request.config_id).first()
    if not config:
        return StreamingResponse(
            iter([f"data: {json.dumps({'content': '未找到指定配置。'})}\n\n", "data: [DONE]\n\n"]),
            media_type="text/event-stream"
        )

    # 2. 获取适配器
    adapter = await _get_adapter_for_config(request.config_id, db)
    if not adapter:
        # 连接失败或无配置
        error_msg = "连接 OpenClaw 服务失败，请前往设置页面配置连接信息。"
        return StreamingResponse(
            iter([f"data: {json.dumps({'content': error_msg})}\n\n", "data: [DONE]\n\n"]),
            media_type="text/event-stream"
        )

    return StreamingResponse(
        openclaw_stream_generator(adapter, request.message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # 禁用 Nginx 缓存
        }
    )
