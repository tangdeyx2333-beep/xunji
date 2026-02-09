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
from app.models.sql_models import OpenClawConfig

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
# user_id -> Adapter 实例
active_connections: Dict[str, "OpenClawChatWsAdapter"] = {}
# user_id -> SSH Tunnel 实例
active_tunnels: Dict[str, "SSHTunnelForwarder"] = {}


# --- 请求模型 ---

class OpenClawConnectRequest(BaseModel):
    user_id: str
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


class OpenClawChatRequest(BaseModel):
    user_id: Optional[str] = None  # 如果未提供，可能无法找到对应连接
    message: str


# --- 辅助函数 ---

def cleanup_connection(user_id: str):
    """清理指定用户的活跃连接和隧道"""
    if user_id in active_connections:
        try:
            adapter = active_connections[user_id]
            adapter.stop()
        except Exception as e:
            print(f"Error stopping adapter for user {user_id}: {e}")
        del active_connections[user_id]

    if user_id in active_tunnels:
        try:
            tunnel = active_tunnels[user_id]
            tunnel.stop()
        except Exception as e:
            print(f"Error stopping tunnel for user {user_id}: {e}")
        del active_tunnels[user_id]


def _create_adapter_settings(config: OpenClawConnectRequest, override_url: Optional[str] = None) -> "AdapterSettings":
    """构造 OpenClaw AdapterSettings"""
    if AdapterSettings is None:
        raise RuntimeError("OpenClaw library not installed")
    
    return AdapterSettings(
        url=override_url or config.gateway_url,
        token=config.gateway_token,
        password=config.gateway_password,
        session_key=config.session_key
    )


# --- 接口实现 ---

@router.post("/connect")
async def connect_openclaw(request: OpenClawConnectRequest, db: Session = Depends(get_db)):
    """
    建立 OpenClaw 连接并持久化配置。
    支持 SSH 隧道。
    """

    if active_tunnels.get(request.user_id) is not None:
        return {"message": "SSH 已建立"}
    if OpenClawChatWsAdapter is None:
        raise HTTPException(status_code=500, detail="后端缺少 openclaw_webchat_adapter 依赖")

    user_id = request.user_id

    # 1. 清理旧连接
    cleanup_connection(user_id)

    tunnel = None
    final_gateway_url = request.gateway_url

    try:
        # 2. 建立 SSH 隧道 (如果需要)
        if request.use_ssh:
            if SSHTunnelForwarder is None:
                raise HTTPException(status_code=500, detail="后端缺少 sshtunnel 依赖，无法建立 SSH 隧道")

            try:
                # 解析网关 URL 获取目标端口
                parsed_url = urlparse(request.gateway_url)
                remote_host = parsed_url.hostname or "127.0.0.1"
                remote_port = parsed_url.port or 18789

                tunnel = SSHTunnelForwarder(
                    (request.ssh_host, request.ssh_port),
                    ssh_username=request.ssh_user,
                    ssh_password=request.ssh_password,
                    remote_bind_address=("127.0.0.1", remote_port), # 映射到远程服务器的 127.0.0.1
                    local_bind_address=('127.0.0.1', request.ssh_local_port), # 0 为随机
                    set_keepalive=30.0
                )
                tunnel.start()
                
                # 更新网关 URL 指向本地隧道端口
                local_port = tunnel.local_bind_port
                final_gateway_url = f"{parsed_url.scheme}://127.0.0.1:{local_port}{parsed_url.path}"
                print(f"SSH Tunnel established for user {user_id}: 127.0.0.1:{local_port} -> {request.ssh_host} -> 127.0.0.1:{remote_port}")
            
            except Exception as e:
                error_str = str(e)
                print(f"SSH Tunnel failed: {error_str}")
                
                # 针对常见配置错误给出更友好的提示
                if "SSH protocol banner" in error_str:
                    detail = f"SSH 建立失败：无法读取协议横幅。这通常是因为 SSH 端口 ({request.ssh_port}) 配置错误，该端口可能不是 SSH 服务（例如误填了网关端口）。请检查 SSH 端口是否应为 22。"
                elif "Connection refused" in error_str:
                    detail = f"SSH 建立失败：连接被拒绝。请检查 IP ({request.ssh_host}) 和端口 ({request.ssh_port}) 是否正确，以及防火墙是否放行。"
                elif "Authentication failed" in error_str:
                    detail = "SSH 建立失败：认证失败。请检查 SSH 用户名和密码是否正确。"
                else:
                    detail = f"SSH 隧道建立失败。错误: {error_str}"
                
                raise HTTPException(status_code=400, detail=detail)

        # 3. 建立 OpenClaw 连接
        try:
            settings = AdapterSettings(
                url=final_gateway_url,
                token=request.gateway_token,
                password=request.gateway_password,
                session_key=request.session_key
            )
            
            adapter = OpenClawChatWsAdapter.create_connected(settings=settings)
            
        except Exception as e:
            # 如果连接失败，且建立了隧道，需要关闭隧道
            if tunnel:
                tunnel.stop()
            
            error_msg = str(e)
            detail_msg = f"连接 OpenClaw 服务失败: {error_msg}。"
            if request.use_ssh:
                detail_msg += " SSH 隧道已建立，但 OpenClaw 握手失败。请确认远程服务器上的 OpenClaw 服务是否正常运行。"
            else:
                detail_msg += " 请检查 URL 是否连通或信息是否正确。"
                
            raise HTTPException(status_code=400, detail=detail_msg)

        # 4. 成功：缓存连接
        active_connections[user_id] = adapter
        if tunnel:
            active_tunnels[user_id] = tunnel

        # 5. 持久化配置到数据库
        db_config = db.query(OpenClawConfig).filter(OpenClawConfig.user_id == user_id).first()
        if not db_config:
            db_config = OpenClawConfig(user_id=user_id)
            db.add(db_config)
        
        # 更新字段
        db_config.gateway_url = request.gateway_url
        db_config.gateway_token = request.gateway_token
        db_config.gateway_password = request.gateway_password
        db_config.session_key = request.session_key
        db_config.use_ssh = request.use_ssh
        db_config.ssh_host = request.ssh_host
        db_config.ssh_port = request.ssh_port
        db_config.ssh_user = request.ssh_user
        db_config.ssh_password = request.ssh_password
        db_config.ssh_local_port = request.ssh_local_port
        db_config.updated_at = datetime.now()
        
        db.commit()
        db.refresh(db_config)

        return {"status": "connected", "user_id": user_id, "message": "OpenClaw 连接成功并已保存配置"}

    except HTTPException:
        raise
    except Exception as e:
        # 兜底异常处理
        if tunnel:
            tunnel.stop()
        cleanup_connection(user_id)
        raise HTTPException(status_code=500, detail=f"OpenClaw 连接过程中发生未知错误: {str(e)}")


async def _get_adapter_for_user(user_id: str, db: Session) -> Optional["OpenClawChatWsAdapter"]:
    """获取用户的 Adapter，如果内存没有则尝试从 DB 恢复"""
    
    # 1. 查内存
    if user_id in active_connections:
        return active_connections[user_id]

    # 2. 查数据库
    config = db.query(OpenClawConfig).filter(OpenClawConfig.user_id == user_id).first()
    if not config:
        return None

    print(f"Restoring OpenClaw connection for user {user_id} from database...")

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
        active_connections[user_id] = adapter
        if tunnel:
            active_tunnels[user_id] = tunnel
        
        return adapter

    except Exception as e:
        print(f"Failed to restore connection for user {user_id}: {e}")
        if tunnel:
            try:
                tunnel.stop()
            except:
                pass
        return None


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
    优先使用 user_id 对应的连接。
    """
    if not request.user_id:
         # 如果没有 user_id，暂时不支持（或者可以回退到旧的全局模式，但根据需求，建议强制 user_id）
         # 为了兼容性，如果内存里没有，我们报错。
         return StreamingResponse(
            iter([f"data: {json.dumps({'content': '请求缺少 user_id，无法定位连接配置。'})}\n\n", "data: [DONE]\n\n"]),
            media_type="text/event-stream"
        )

    adapter = await _get_adapter_for_user(request.user_id, db)

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
