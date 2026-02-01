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

    #  新增：必须存储加密后的密码
    hashed_password = Column(String(100), nullable=False)
    # 对应草图: delete (是否注销 0未 1是) -> 建议用 Boolean
    is_deleted = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.now)

    # 关联关系
    conversations = relationship("Conversation", back_populates="user")
    files = relationship("FileRecord", back_populates="user")


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
