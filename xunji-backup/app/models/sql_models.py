from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Boolean, Integer
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
import uuid

Base = declarative_base()


def gen_uuid():
    return str(uuid.uuid4())


# --- 1. 用户表 (User) ---
class User(Base):
    __tablename__ = "users"

    # 对应草图: id String 唯一标识
    id = Column(String, primary_key=True, default=gen_uuid)

    # 对应草图: name, email
    username = Column(String, unique=True, index=True, nullable=True)
    email = Column(String, nullable=True)

    # 设备指纹，用于匿名用户识别
    device_id = Column(String, unique=True, index=True, nullable=True)
    
    #  新增：存储加密后的密码（可为空，支持无密码的匿名用户）
    hashed_password = Column(String(100), nullable=True)
    
    # 是否为匿名用户（自动创建的用户）
    is_anonymous = Column(Boolean, default=True)
    
    # 对应草图: delete (是否注销 0未 1是) -> 建议用 Boolean
    is_deleted = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.now)

    # 关联关系
    conversations = relationship("Conversation", back_populates="user")
    files = relationship("FileRecord", back_populates="user")
    openclaw_config = relationship("OpenClawConfig", back_populates="user", uselist=False)


# --- 2. 会话表 (Conversation) ---
class Conversation(Base):
    __tablename__ = "conversations"

    # 对应草图: id String
    id = Column(String, primary_key=True, default=gen_uuid)

    # 对应草图: title, update_time, create_time
    title = Column(String, default="新对话")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # 对应草图: user_id 外键
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    is_deleted = Column(Boolean, default=False)

    # 关联关系
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


# --- 3. 聊天消息表 (Message) ---
class Message(Base):
    __tablename__ = "messages"

    # 对应草图: id String
    id = Column(String, primary_key=True, default=gen_uuid)

    # 对应草图: session_id (我们会话表叫 conversation)
    conversation_id = Column(String, ForeignKey("conversations.id"))

    # 对应草图: role, content, type
    role = Column(String)  # user / ai / system
    content = Column(Text)  # 消息内容
    type = Column(String, default="text")  # text, thought, chain

    # 对应草图: token_count (你标记为可选，建议加上，很有用)
    token_count = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.now)


    # 关联关系
    conversation = relationship("Conversation", back_populates="messages")
    attachments = relationship("MessageAttachment", back_populates="message", cascade="all, delete-orphan")


# --- 4. 文档表 (FileRecord) ---
class FileRecord(Base):
    __tablename__ = "files"

    # 这个 ID 同时也是 ChromaDB 里的 file_id
    id = Column(String, primary_key=True, default=gen_uuid)

    # 对应草图: user_id
    user_id = Column(String, ForeignKey("users.id"), nullable=True)

    # 对应草图: file_name
    filename = Column(String)

    # 对应草图: file_path (其实就是上面的 id，这里可以存文件物理路径做备份)
    file_path = Column(String)

    # 文件的大小
    file_size = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.now)
    is_deleted = Column(Boolean, default=False)

    # 关联关系
    user = relationship("User", back_populates="files")


# --- 5. 树状节点表 (TreeNode) ---
class TreeNode(Base):
    __tablename__ = "tree_nodes"

    id = Column(String, primary_key=True, default=gen_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id"))
    
    # 消息ID
    message_id = Column(String, ForeignKey("messages.id"))
    
    # 父节点ID (实现树状结构)
    parent_id = Column(String, ForeignKey("tree_nodes.id"), nullable=True)
    
    created_at = Column(DateTime, default=datetime.now)

    # 关联
    message = relationship("Message")
    parent = relationship("TreeNode", remote_side=[id], backref="children")

    created_at = Column(DateTime, default=datetime.now)

    is_deleted = Column(Boolean, default=False)


# --- 6. 模型配置表 (ModelConfig) ---
class ModelConfig(Base):
    __tablename__ = "model_configs"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)  # 绑定用户，如果为空则为系统默认
    
    model_name = Column(String, nullable=False)  # 实际调用的模型名，如 gpt-4
    display_name = Column(String, nullable=False) # 显示名称，如 GPT-4
    
    created_at = Column(DateTime, default=datetime.now)
    
    # 关联
    user = relationship("User")


class AiInstruction(Base):
    __tablename__ = "ai_instructions"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)

    content = Column(Text, nullable=False)
    sort_order = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    is_deleted = Column(Boolean, default=False)

    user = relationship("User")


class ConversationAiInstruction(Base):
    __tablename__ = "conversation_ai_instructions"

    id = Column(String, primary_key=True, default=gen_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)

    content = Column(Text, nullable=False)
    sort_order = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    is_deleted = Column(Boolean, default=False)

    user = relationship("User")
    conversation = relationship("Conversation")


class MessageAttachment(Base):
    __tablename__ = "message_attachments"

    id = Column(String, primary_key=True, default=gen_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id"))
    message_id = Column(String, ForeignKey("messages.id"))
    user_id = Column(String, ForeignKey("users.id"), nullable=True)

    filename = Column(String, nullable=False)
    mime = Column(String, default="")
    size = Column(Integer, default=0)

    storage_provider = Column(String, default="cos")
    storage_key = Column(String, nullable=False)
    url = Column(String, nullable=False)

    created_at = Column(DateTime, default=datetime.now)

    message = relationship("Message", back_populates="attachments")


class OpenClawConfig(Base):
    __tablename__ = "openclaw_configs"

    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)

    display_name = Column(String, nullable=False, default="默认 OpenClaw", server_default="默认 OpenClaw")

    gateway_url = Column(String, nullable=False)
    gateway_token = Column(String, nullable=True)
    gateway_password = Column(String, nullable=True)
    session_key = Column(String, nullable=False)

    use_ssh = Column(Boolean, default=False)
    ssh_host = Column(String, nullable=True)
    ssh_port = Column(Integer, default=22)
    ssh_user = Column(String, nullable=True)
    ssh_password = Column(String, nullable=True)
    ssh_local_port = Column(Integer, default=0)

    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    created_at = Column(DateTime, default=datetime.now)

    user = relationship("User", back_populates="openclaw_config")
