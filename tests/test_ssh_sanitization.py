from pydantic import BaseModel, model_validator
from typing import Optional
from urllib.parse import urlparse

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
    ssh_local_port: int = 0

    @model_validator(mode='after')
    def check_auth(self):
        if self.use_ssh:
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

def test_sanitization():
    # 测试数据 1: 带 http 和末尾斜杠
    req1 = OpenClawConnectRequest(
        user_id="test",
        gateway_url="ws://127.0.0.1:18789",
        session_key="key",
        use_ssh=True,
        ssh_host="http://49.234.46.94/",
        ssh_user="root",
        ssh_password="pwd"
    )
    print(f"Input: http://49.234.46.94/ -> Sanitized: {req1.ssh_host}")
    assert req1.ssh_host == "49.234.46.94"

    # 测试数据 2: 带 https
    req2 = OpenClawConnectRequest(
        user_id="test",
        gateway_url="ws://127.0.0.1:18789",
        session_key="key",
        use_ssh=True,
        ssh_host="https://myserver.com",
        ssh_user="root",
        ssh_password="pwd"
    )
    print(f"Input: https://myserver.com -> Sanitized: {req2.ssh_host}")
    assert req2.ssh_host == "myserver.com"

    # 测试数据 3: 纯 IP
    req3 = OpenClawConnectRequest(
        user_id="test",
        gateway_url="ws://127.0.0.1:18789",
        session_key="key",
        use_ssh=True,
        ssh_host="1.2.3.4",
        ssh_user="root",
        ssh_password="pwd"
    )
    print(f"Input: 1.2.3.4 -> Sanitized: {req3.ssh_host}")
    assert req3.ssh_host == "1.2.3.4"

if __name__ == "__main__":
    test_sanitization()
    print("All tests passed!")
