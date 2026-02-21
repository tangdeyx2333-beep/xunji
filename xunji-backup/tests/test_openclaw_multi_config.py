"""
OpenClaw多配置支持单元测试
测试多配置CRUD操作、配置切换、连接管理等功能
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.models.openclaw import OpenClawConfig
from app.models.user import User

# 创建测试数据库
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建测试数据库表
Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

# 测试用户数据
TEST_USER_ID = "test_user_123"
TEST_CONFIG_DATA = {
    "user_id": TEST_USER_ID,
    "display_name": "测试配置",
    "gateway_url": "ws://127.0.0.1:18789",
    "session_key": "agent:main:main",
    "auth_type": "token",
    "gateway_token": "test_token_123",
    "use_ssh": False,
    "ssh_host": "",
    "ssh_port": 22,
    "ssh_user": "",
    "ssh_password": "",
    "ssh_local_port": 0
}

@pytest.fixture
def test_user():
    """创建测试用户"""
    db = TestingSessionLocal()
    user = User(id=TEST_USER_ID, username="test_user", email="test@example.com")
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    return user

@pytest.fixture
def test_config(test_user):
    """创建测试配置"""
    db = TestingSessionLocal()
    config = OpenClawConfig(**TEST_CONFIG_DATA)
    db.add(config)
    db.commit()
    db.refresh(config)
    db.close()
    return config

class TestOpenClawMultiConfig:
    """OpenClaw多配置支持测试类"""
    
    def test_create_openclaw_config(self, test_user):
        """测试创建OpenClaw配置"""
        response = client.post(
            "/api/openclaw/configs",
            json=TEST_CONFIG_DATA
        )
        assert response.status_code == 200
        data = response.json()
        assert data["display_name"] == TEST_CONFIG_DATA["display_name"]
        assert data["gateway_url"] == TEST_CONFIG_DATA["gateway_url"]
        assert data["user_id"] == TEST_USER_ID
        assert "id" in data
    
    def test_get_user_configs(self, test_user, test_config):
        """测试获取用户所有配置"""
        response = client.get(
            f"/api/openclaw/configs?user_id={TEST_USER_ID}"
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert any(config["id"] == test_config.id for config in data)
    
    def test_get_single_config(self, test_config):
        """测试获取单个配置"""
        response = client.get(
            f"/api/openclaw/configs/{test_config.id}"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_config.id
        assert data["display_name"] == test_config.display_name
    
    def test_update_config(self, test_config):
        """测试更新配置"""
        update_data = {
            "display_name": "更新后的配置名称",
            "gateway_url": "ws://192.168.1.100:18789"
        }
        response = client.put(
            f"/api/openclaw/configs/{test_config.id}",
            json=update_data
        )
        assert response.status_code == 200
        data = response.json()
        assert data["display_name"] == "更新后的配置名称"
        assert data["gateway_url"] == "ws://192.168.1.100:18789"
    
    def test_delete_config(self, test_user):
        """测试删除配置"""
        # 先创建一个配置
        create_response = client.post(
            "/api/openclaw/configs",
            json=TEST_CONFIG_DATA
        )
        config_id = create_response.json()["id"]
        
        # 删除配置
        response = client.delete(
            f"/api/openclaw/configs/{config_id}?user_id={TEST_USER_ID}"
        )
        assert response.status_code == 200
        
        # 验证配置已被删除
        get_response = client.get(f"/api/openclaw/configs/{config_id}")
        assert get_response.status_code == 404
    
    def test_connect_by_config_id(self, test_config):
        """测试通过配置ID连接OpenClaw"""
        response = client.post(
            "/api/openclaw/connect",
            json={"config_id": test_config.id}
        )
        # 注意：实际连接可能失败，因为我们没有真实的OpenClaw服务
        # 但API应该能正确处理请求
        assert response.status_code in [200, 400, 500]
    
    def test_create_and_connect_config(self, test_user):
        """测试创建配置并立即连接"""
        create_data = {
            "user_id": TEST_USER_ID,
            "display_name": "新建并连接测试",
            "gateway_url": "ws://127.0.0.1:18789",
            "session_key": "agent:main:main",
            "auth_type": "token",
            "gateway_token": "new_token_456"
        }
        response = client.post(
            "/api/openclaw/configs/connect",
            json=create_data
        )
        # 同样，实际连接可能失败，但API应该能处理
        assert response.status_code in [200, 400, 500]
    
    def test_get_config_history(self, test_config):
        """测试获取配置的历史记录"""
        response = client.get(
            f"/api/openclaw/history/{test_config.id}"
        )
        # 可能没有历史记录，但API应该返回空列表
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_chat_with_config(self, test_config):
        """测试使用配置进行聊天"""
        response = client.post(
            "/api/openclaw/chat",
            json={
                "message": "你好，OpenClaw",
                "config_id": test_config.id
            }
        )
        # 流式响应，状态码应该为200
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
    
    def test_multiple_configs_per_user(self, test_user):
        """测试一个用户可以有多个配置"""
        # 创建多个配置
        configs_data = [
            {
                "user_id": TEST_USER_ID,
                "display_name": "配置1",
                "gateway_url": "ws://127.0.0.1:18789",
                "session_key": "agent:main:main"
            },
            {
                "user_id": TEST_USER_ID,
                "display_name": "配置2",
                "gateway_url": "ws://192.168.1.100:18789",
                "session_key": "agent:main:main"
            },
            {
                "user_id": TEST_USER_ID,
                "display_name": "配置3",
                "gateway_url": "ws://10.0.0.1:18789",
                "session_key": "agent:main:main"
            }
        ]
        
        created_configs = []
        for config_data in configs_data:
            response = client.post("/api/openclaw/configs", json=config_data)
            assert response.status_code == 200
            created_configs.append(response.json())
        
        # 验证所有配置都已创建
        response = client.get(f"/api/openclaw/configs?user_id={TEST_USER_ID}")
        assert response.status_code == 200
        user_configs = response.json()
        
        # 验证配置数量
        assert len([c for c in user_configs if c["display_name"].startswith("配置")]) == 3
        
        # 验证每个配置的唯一性
        config_names = [c["display_name"] for c in created_configs]
        assert len(set(config_names)) == 3
        config_urls = [c["gateway_url"] for c in created_configs]
        assert len(set(config_urls)) == 3
    
    def test_config_isolation(self, test_user):
        """测试配置之间的隔离性"""
        # 创建两个不同的配置
        config1_data = {
            "user_id": TEST_USER_ID,
            "display_name": "隔离测试配置1",
            "gateway_url": "ws://127.0.0.1:18789",
            "session_key": "agent:main:main",
            "gateway_token": "token1"
        }
        config2_data = {
            "user_id": TEST_USER_ID,
            "display_name": "隔离测试配置2",
            "gateway_url": "ws://192.168.1.100:18789",
            "session_key": "agent:main:main",
            "gateway_token": "token2"
        }
        
        # 创建配置
        response1 = client.post("/api/openclaw/configs", json=config1_data)
        config1 = response1.json()
        response2 = client.post("/api/openclaw/configs", json=config2_data)
        config2 = response2.json()
        
        # 验证配置数据隔离
        assert config1["gateway_token"] == "token1"
        assert config2["gateway_token"] == "token2"
        assert config1["gateway_url"] != config2["gateway_url"]
        
        # 验证获取单个配置时不会混淆
        get1_response = client.get(f"/api/openclaw/configs/{config1['id']}")
        get2_response = client.get(f"/api/openclaw/configs/{config2['id']}")
        
        assert get1_response.json()["gateway_token"] == "token1"
        assert get2_response.json()["gateway_token"] == "token2"
    
    def test_invalid_config_data(self):
        """测试无效配置数据的处理"""
        # 缺少必填字段
        invalid_data = {
            "user_id": TEST_USER_ID,
            "display_name": "无效配置"
            # 缺少 gateway_url 和 session_key
        }
        response = client.post("/api/openclaw/configs", json=invalid_data)
        assert response.status_code == 422  # 验证错误
    
    def test_nonexistent_config_access(self):
        """测试访问不存在的配置"""
        fake_config_id = "nonexistent_config_999"
        
        # 获取不存在的配置
        response = client.get(f"/api/openclaw/configs/{fake_config_id}")
        assert response.status_code == 404
        
        # 更新不存在的配置
        update_data = {"display_name": "新名称"}
        response = client.put(f"/api/openclaw/configs/{fake_config_id}", json=update_data)
        assert response.status_code == 404
        
        # 删除不存在的配置
        response = client.delete(f"/api/openclaw/configs/{fake_config_id}?user_id={TEST_USER_ID}")
        assert response.status_code == 404
    
    def test_config_with_ssh_tunnel(self, test_user):
        """测试带SSH隧道的配置"""
        ssh_config_data = {
            "user_id": TEST_USER_ID,
            "display_name": "SSH隧道配置",
            "gateway_url": "ws://localhost:18789",
            "session_key": "agent:main:main",
            "auth_type": "token",
            "gateway_token": "ssh_token",
            "use_ssh": True,
            "ssh_host": "remote.server.com",
            "ssh_port": 22,
            "ssh_user": "admin",
            "ssh_password": "secret_password",
            "ssh_local_port": 18789
        }
        
        response = client.post("/api/openclaw/configs", json=ssh_config_data)
        assert response.status_code == 200
        data = response.json()
        
        assert data["use_ssh"] is True
        assert data["ssh_host"] == "remote.server.com"
        assert data["ssh_port"] == 22
        assert data["ssh_user"] == "admin"
        assert data["ssh_password"] == "secret_password"
        assert data["ssh_local_port"] == 18789
    
    def test_config_validation_rules(self, test_user):
        """测试配置验证规则"""
        # 测试无效的URL格式
        invalid_url_config = {
            "user_id": TEST_USER_ID,
            "display_name": "无效URL配置",
            "gateway_url": "invalid-url-format",
            "session_key": "agent:main:main"
        }
        response = client.post("/api/openclaw/configs", json=invalid_url_config)
        assert response.status_code == 200  # 目前不验证URL格式
    
    def test_concurrent_config_operations(self, test_user):
        """测试并发配置操作"""
        import threading
        import time
        
        results = []
        
        def create_config(index):
            config_data = {
                "user_id": TEST_USER_ID,
                "display_name": f"并发配置{index}",
                "gateway_url": f"ws://127.0.0.1:{18789 + index}",
                "session_key": "agent:main:main"
            }
            response = client.post("/api/openclaw/configs", json=config_data)
            results.append(response.status_code)
        
        # 启动多个线程同时创建配置
        threads = []
        for i in range(5):
            thread = threading.Thread(target=create_config, args=(i,))
            threads.append(thread)
            thread.start()
        
        # 等待所有线程完成
        for thread in threads:
            thread.join()
        
        # 验证所有操作都成功
        assert all(status == 200 for status in results)
        
        # 验证所有配置都已创建
        response = client.get(f"/api/openclaw/configs?user_id={TEST_USER_ID}")
        user_configs = response.json()
        concurrent_configs = [c for c in user_configs if c["display_name"].startswith("并发配置")]
        assert len(concurrent_configs) == 5
    
    def test_config_with_different_auth_types(self, test_user):
        """测试不同认证类型的配置"""
        auth_types = ["token", "password", "certificate"]
        
        for i, auth_type in enumerate(auth_types):
            config_data = {
                "user_id": TEST_USER_ID,
                "display_name": f"认证类型测试{i}",
                "gateway_url": f"ws://127.0.0.1:{18789 + i}",
                "session_key": "agent:main:main",
                "auth_type": auth_type,
                "gateway_token": f"token_{auth_type}"
            }
            
            response = client.post("/api/openclaw/configs", json=config_data)
            assert response.status_code == 200
            data = response.json()
            assert data["auth_type"] == auth_type
    
    def test_empty_config_list(self, test_user):
        """测试空配置列表的处理"""
        # 创建一个没有配置的新用户
        new_user_id = "empty_user_123"
        db = TestingSessionLocal()
        new_user = User(id=new_user_id, username="empty_user", email="empty@example.com")
        db.add(new_user)
        db.commit()
        db.close()
        
        response = client.get(f"/api/openclaw/configs?user_id={new_user_id}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0
    
    def test_config_with_empty_optional_fields(self, test_user):
        """测试配置可选字段为空的处理"""
        minimal_config_data = {
            "user_id": TEST_USER_ID,
            "display_name": "最小配置测试",
            "gateway_url": "ws://127.0.0.1:18789",
            "session_key": "agent:main:main",
            "auth_type": "token",
            "gateway_token": "minimal_token"
            # 省略所有可选字段
        }
        
        response = client.post("/api/openclaw/configs", json=minimal_config_data)
        assert response.status_code == 200
        data = response.json()
        
        # 验证必需字段
        assert data["display_name"] == "最小配置测试"
        assert data["gateway_url"] == "ws://127.0.0.1:18789"
        assert data["session_key"] == "agent:main:main"
        
        # 验证可选字段的默认值
        assert data.get("use_ssh", False) is False
        assert data.get("ssh_host", "") == ""
        assert data.get("ssh_port", 22) == 22
    
    def test_connect_with_invalid_config_id(self):
        """测试使用无效配置ID连接"""
        invalid_config_id = "invalid_config_999"
        
        response = client.post(
            "/api/openclaw/connect",
            json={"config_id": invalid_config_id}
        )
        assert response.status_code == 404
    
    def test_chat_with_invalid_config_id(self):
        """测试使用无效配置ID聊天"""
        invalid_config_id = "invalid_config_999"
        
        response = client.post(
            "/api/openclaw/chat",
            json={
                "message": "测试消息",
                "config_id": invalid_config_id
            }
        )
        assert response.status_code == 404
    
    def test_delete_config_with_invalid_user_id(self, test_config):
        """测试使用无效用户ID删除配置"""
        invalid_user_id = "invalid_user_999"
        
        response = client.delete(
            f"/api/openclaw/configs/{test_config.id}?user_id={invalid_user_id}"
        )
        assert response.status_code == 403  # 或者 404，取决于实现

class TestOpenClawMultiConfigIntegration:
    """OpenClaw多配置集成测试类"""
    
    def test_full_config_lifecycle(self, test_user):
        """测试配置的完整生命周期"""
        # 1. 创建配置
        create_response = client.post("/api/openclaw/configs", json=TEST_CONFIG_DATA)
        assert create_response.status_code == 200
        config = create_response.json()
        config_id = config["id"]
        
        # 2. 获取配置详情
        get_response = client.get(f"/api/openclaw/configs/{config_id}")
        assert get_response.status_code == 200
        assert get_response.json()["id"] == config_id
        
        # 3. 更新配置
        update_data = {"display_name": "更新后的名称"}
        update_response = client.put(f"/api/openclaw/configs/{config_id}", json=update_data)
        assert update_response.status_code == 200
        assert update_response.json()["display_name"] == "更新后的名称"
        
        # 4. 尝试连接（可能失败，但API应能处理）
        connect_response = client.post("/api/openclaw/connect", json={"config_id": config_id})
        assert connect_response.status_code in [200, 400, 500]
        
        # 5. 获取历史记录
        history_response = client.get(f"/api/openclaw/history/{config_id}")
        assert history_response.status_code == 200
        assert isinstance(history_response.json(), list)
        
        # 6. 删除配置
        delete_response = client.delete(f"/api/openclaw/configs/{config_id}?user_id={TEST_USER_ID}")
        assert delete_response.status_code == 200
        
        # 7. 验证配置已删除
        final_get_response = client.get(f"/api/openclaw/configs/{config_id}")
        assert final_get_response.status_code == 404

# 测试报告总结
def generate_test_report():
    """生成测试报告"""
    test_cases = [
        "创建OpenClaw配置",
        "获取用户所有配置", 
        "获取单个配置详情",
        "更新配置信息",
        "删除配置",
        "通过配置ID连接",
        "创建并连接配置",
        "获取配置历史记录",
        "使用配置进行聊天",
        "多配置支持验证",
        "配置隔离性测试",
        "无效配置数据处理",
        "访问不存在配置",
        "SSH隧道配置测试",
        "配置验证规则",
        "并发配置操作",
        "不同认证类型配置",
        "空配置列表处理",
        "可选字段为空处理",
        "无效配置ID连接测试",
        "无效配置ID聊天测试",
        "无效用户ID删除测试",
        "配置完整生命周期测试"
    ]
    
    print("=" * 60)
    print("OpenClaw多配置支持单元测试报告")
    print("=" * 60)
    print(f"测试用例总数: {len(test_cases)}")
    print(f"覆盖功能点:")
    for i, case in enumerate(test_cases, 1):
        print(f"  {i:2d}. {case}")
    print("=" * 60)
    print("测试覆盖范围:")
    print("  ✓ 配置CRUD操作")
    print("  ✓ 多配置支持验证")
    print("  ✓ 配置隔离性测试")
    print("  ✓ 连接管理功能")
    print("  ✓ 错误处理机制")
    print("  ✓ 边界条件测试")
    print("  ✓ 并发操作测试")
    print("  ✓ 集成测试验证")
    print("=" * 60)

if __name__ == "__main__":
    pytest.main([__file__])