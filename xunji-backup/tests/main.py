import uvicorn
from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, text, Boolean
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from pydantic import BaseModel
from typing import List, Optional

# ==========================================
# 1. 数据库配置 (SQLite)
# ==========================================
DATABASE_URL = "sqlite:///./test_tree_v3.db"

# connect_args={"check_same_thread": False} 是 SQLite 在多线程环境(FastAPI)下的必须配置
engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# ==========================================
# 2. 数据库模型 (Models)
# ==========================================

class Message(Base):
    """
    内容表
    """
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    content = Column(Text)


class TreeNode(Base):
    """
    树结构表
    """
    __tablename__ = "tree_nodes"

    # 注意：为了满足你测试用例中 ID=0 的需求，这里不强制自增，允许手动指定 ID
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String, index=True, nullable=False)

    parent_id = Column(Integer, ForeignKey("tree_nodes.id"), nullable=True)
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=False)
    node_name = Column(String)

    # [新增] 伪删除标记：True 表示已删除
    is_deleted = Column(Boolean, default=False, index=True)

    message = relationship("Message")
    children = relationship("TreeNode", backref="parent", remote_side=[id])


# 初始化数据库表
Base.metadata.create_all(bind=engine)


# ==========================================
# 3. Pydantic 数据传输模型 (Schemas)
# ==========================================

class MessageCreate(BaseModel):
    title: str
    content: str


class TreeNodeCreate(BaseModel):
    session_id: str
    parent_id: Optional[int] = None
    message_id: int
    node_name: str


class TreeNodeResponse(BaseModel):
    id: int
    session_id: str
    parent_id: Optional[int]
    node_name: str
    message_title: str
    depth: int

    class Config:
        from_attributes = True


# ==========================================
# 4. FastAPI 应用与接口
# ==========================================

app = FastAPI(title="Tree Session Demo V3")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.post("/messages/", response_model=dict)
def create_message(msg: MessageCreate, db: Session = Depends(get_db)):
    db_msg = Message(title=msg.title, content=msg.content)
    db.add(db_msg)
    db.commit()
    db.refresh(db_msg)
    return {"status": "success", "message_id": db_msg.id, "title": db_msg.title}


@app.post("/nodes/", response_model=dict)
def mount_node(node: TreeNodeCreate, db: Session = Depends(get_db)):
    """
    挂载节点
    Requirement 1: 相同的 message_id 不能重复添加 (在同一个 session 内)
    """

    # 1. 检查 message 是否存在
    msg = db.query(Message).filter(Message.id == node.message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    # [新增] Requirement 1: 防重检查
    # 检查当前 Session 下，是否已经有该 message_id，且未被删除
    duplicate_check = db.query(TreeNode).filter(
        TreeNode.session_id == node.session_id,
        TreeNode.message_id == node.message_id,
        TreeNode.is_deleted == False
    ).first()

    if duplicate_check:
        raise HTTPException(
            status_code=400,
            detail=f"Message {node.message_id} already exists in session {node.session_id}"
        )

    # 2. 检查父节点逻辑
    if node.parent_id is not None:
        parent = db.query(TreeNode).filter(
            TreeNode.id == node.parent_id,
            TreeNode.is_deleted == False  # 父节点也不能是已删除的
        ).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Parent node not found or deleted")

        if parent.session_id != node.session_id:
            raise HTTPException(status_code=400, detail="Node session_id mismatch with parent session_id")
    else:
        # 根节点逻辑：检查是否已有根节点
        existing_root = db.query(TreeNode).filter(
            TreeNode.session_id == node.session_id,
            TreeNode.parent_id == None,
            TreeNode.is_deleted == False
        ).first()
        if existing_root:
            raise HTTPException(status_code=400,
                                detail=f"Active root node already exists for session {node.session_id}")

    # 3. 创建节点
    db_node = TreeNode(
        session_id=node.session_id,
        parent_id=node.parent_id,
        message_id=node.message_id,
        node_name=node.node_name,
        is_deleted=False
    )
    db.add(db_node)
    db.commit()
    db.refresh(db_node)
    return {
        "status": "success",
        "node_id": db_node.id,
        "session_id": db_node.session_id
    }


@app.delete("/nodes/{node_id}", response_model=dict)
def delete_node(node_id: int, db: Session = Depends(get_db)):
    """
    [新增] Requirement 2: 伪删除节点，并级联删除所有子支树
    """
    # 1. 检查节点是否存在（且未删除）
    target_node = db.query(TreeNode).filter(TreeNode.id == node_id, TreeNode.is_deleted == False).first()
    if not target_node:
        raise HTTPException(status_code=404, detail="Node not found or already deleted")

    # 2. 使用递归查找所有子孙节点的 ID
    # 这一步是为了找出所有需要变更 is_deleted 状态的 ID 列表
    subtree_ids_query = text("""
                             WITH RECURSIVE delete_cte AS (
                                 -- Anchor: 目标节点
                                 SELECT id
                                 FROM tree_nodes
                                 WHERE id = :target_id
                                   AND is_deleted = 0

                                 UNION ALL

                                 -- Recursive: 查找子节点
                                 SELECT t.id
                                 FROM tree_nodes t
                                          JOIN delete_cte dt ON t.parent_id = dt.id
                                 WHERE t.is_deleted = 0)
                             SELECT id
                             FROM delete_cte;
                             """)

    result = db.execute(subtree_ids_query, {"target_id": node_id}).fetchall()
    ids_to_delete = [row.id for row in result]

    # 3. 批量更新为已删除
    if ids_to_delete:
        db.query(TreeNode).filter(TreeNode.id.in_(ids_to_delete)).update(
            {TreeNode.is_deleted: True}, synchronize_session=False
        )
        db.commit()

    return {
        "status": "success",
        "message": f"Node {node_id} and its subtree (total {len(ids_to_delete)} nodes) marked as deleted.",
        "deleted_ids": ids_to_delete
    }


@app.get("/sessions/{session_id}", response_model=List[TreeNodeResponse])
def get_session_tree(session_id: str, db: Session = Depends(get_db)):
    """
    获取会话树 (过滤已删除节点)
    """
    root_node = db.query(TreeNode).filter(
        TreeNode.session_id == session_id,
        TreeNode.parent_id == None,
        TreeNode.is_deleted == False  # [过滤]
    ).first()

    if not root_node:
        return []

    recursive_query = text("""
                           WITH RECURSIVE tree_cte AS (SELECT t.id,
                                                              t.session_id,
                                                              t.parent_id,
                                                              t.message_id,
                                                              t.node_name,
                                                              0 as depth
                                                       FROM tree_nodes t
                                                       WHERE t.id = :root_id
                                                         AND t.is_deleted = 0 -- [过滤]

                                                       UNION ALL

                                                       SELECT t.id,
                                                              t.session_id,
                                                              t.parent_id,
                                                              t.message_id,
                                                              t.node_name,
                                                              tc.depth + 1
                                                       FROM tree_nodes t
                                                                JOIN tree_cte tc ON t.parent_id = tc.id
                                                       WHERE t.is_deleted = 0 -- [过滤] 递归过程中也不包含已删除的
                           )
                           SELECT tc.id,
                                  tc.session_id,
                                  tc.parent_id,
                                  tc.node_name,
                                  tc.depth,
                                  m.title as message_title
                           FROM tree_cte tc
                                    JOIN messages m ON tc.message_id = m.id
                           ORDER BY tc.depth, tc.id;
                           """)

    result = db.execute(recursive_query, {"root_id": root_node.id}).fetchall()

    response_data = []
    for row in result:
        response_data.append({
            "id": row.id,
            "session_id": row.session_id,
            "parent_id": row.parent_id,
            "node_name": row.node_name,
            "message_title": row.message_title,
            "depth": row.depth
        })

    return response_data

@app.get("/tree/path/{node_id}", response_model=List[TreeNodeResponse])
def get_node_path(node_id: int, db: Session = Depends(get_db)):
    """
    面包屑导航 (向上递归)，保持不变，增加 session_id 返回
    """
    target_node = db.query(TreeNode).filter(TreeNode.id == node_id).first()
    if not target_node:
        raise HTTPException(status_code=404, detail="Node not found")

    recursive_query = text("""
                           WITH RECURSIVE path_cte AS (SELECT t.id,
                                                              t.session_id,
                                                              t.parent_id,
                                                              t.message_id,
                                                              t.node_name,
                                                              0 as distance
                                                       FROM tree_nodes t
                                                       WHERE t.id = :target_id
                                                         AND t.is_deleted = 0 -- [过滤]


                                                       UNION ALL

                                                       SELECT t.id,
                                                              t.session_id,
                                                              t.parent_id,
                                                              t.message_id,
                                                              t.node_name,
                                                              pc.distance + 1
                                                       FROM tree_nodes t
                                                                JOIN path_cte pc ON t.id = pc.parent_id)
                           SELECT pc.id,
                                  pc.session_id,
                                  pc.parent_id,
                                  pc.node_name,
                                  pc.distance,
                                  m.title as message_title
                           FROM path_cte pc
                                    JOIN messages m ON pc.message_id = m.id
                           ORDER BY pc.distance DESC;
                           """)

    result = db.execute(recursive_query, {"target_id": node_id}).fetchall()

    response_data = []
    for index, row in enumerate(result):
        response_data.append({
            "id": row.id,
            "session_id": row.session_id,
            "parent_id": row.parent_id,
            "node_name": row.node_name,
            "message_title": row.message_title,
            "depth": index
        })

    return response_data
@app.post("/test/init_data")
def create_test_case_data(db: Session = Depends(get_db)):
    """
    [新增] Requirement 3: 自动创建图中的树结构作为测试用例
    结构: 0 -> 1 -> 2 -> (3->5, 4->6)
    根节点 ID 为 0
    """
    session_id = "test_case_graph"

    # 1. 清理旧数据 (如果有冲突)
    # 注意：这里为了演示方便直接删除 ID 0-6 的数据，生产环境请勿这样做
    db.query(TreeNode).filter(TreeNode.id.in_([0, 1, 2, 3, 4, 5, 6])).delete(synchronize_session=False)
    db.commit()

    # 2. 确保有足够的消息 (Message)
    # 创建 7 条消息对应 7 个节点
    msgs = []
    for i in range(7):
        msg = Message(title=f"Msg Content {i}", content=f"Data for node {i}")
        db.add(msg)
        msgs.append(msg)
    db.commit()
    # 刷新获取 ID
    for m in msgs: db.refresh(m)

    # 3. 手动创建节点，强制指定 ID 以符合你的图片要求
    # 结构:
    # 0 (root)
    # 0 -> 1
    # 1 -> 2
    # 2 -> 3
    # 2 -> 4
    # 3 -> 5
    # 4 -> 6

    nodes = [
        TreeNode(id=0, session_id=session_id, parent_id=None, message_id=msgs[0].id, node_name="Node 0 (Root)"),
        TreeNode(id=1, session_id=session_id, parent_id=0, message_id=msgs[1].id, node_name="Node 1"),
        TreeNode(id=2, session_id=session_id, parent_id=1, message_id=msgs[2].id, node_name="Node 2"),
        TreeNode(id=3, session_id=session_id, parent_id=2, message_id=msgs[3].id, node_name="Node 3"),
        TreeNode(id=4, session_id=session_id, parent_id=2, message_id=msgs[4].id, node_name="Node 4"),
        TreeNode(id=5, session_id=session_id, parent_id=3, message_id=msgs[5].id, node_name="Node 5"),
        TreeNode(id=6, session_id=session_id, parent_id=4, message_id=msgs[6].id, node_name="Node 6"),
    ]

    for n in nodes:
        db.add(n)

    try:
        db.commit()
        return {"status": "success", "message": "Test case tree created", "session_id": session_id,
                "structure": "0->1->2->(3->5, 4->6)"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))




if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)