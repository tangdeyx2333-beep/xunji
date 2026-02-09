import unittest

class MockVueComponent:
    """模拟 GeminiLayout.vue 的组件状态"""
    
    def __init__(self):
        # 响应式状态
        self.showSettings = False
        self.showConversationInstructions = False
        self.showChatTree = False
        self.currentConversationId = None
        self.isOpenClawMode = False

    def switchSession(self, session_id):
        """
        模拟切换会话的方法 (switchSession)
        具体做了什么: 切换会话上下文，并确保所有 UI 覆盖层关闭。
        """
        if self.isOpenClawMode:
            self.isOpenClawMode = False
        
        # 修复点：显式关闭 UI 状态
        self.showSettings = False
        self.showConversationInstructions = False
        self.showChatTree = False
        
        if self.currentConversationId == session_id:
            return
            
        self.currentConversationId = session_id

    def startNewChat(self):
        """
        模拟开启新会话的方法 (startNewChat)
        具体做了什么: 重置当前会话 ID，并确保所有 UI 覆盖层关闭。
        """
        if self.isOpenClawMode:
            self.isOpenClawMode = False
            
        # 修复点：显式关闭 UI 状态
        self.showSettings = False
        self.showConversationInstructions = False
        self.showChatTree = False
        
        self.currentConversationId = None

class TestUILogic(unittest.TestCase):
    """
    测试 GeminiLayout.vue 的 UI 状态管理逻辑
    """

    def setUp(self):
        self.view = MockVueComponent()

    def test_switch_session_closes_all_ui(self):
        """测试切换会话时是否关闭了所有 UI 覆盖层"""
        # 1. 模拟用户打开了设置面板
        self.view.showSettings = True
        self.view.showConversationInstructions = True
        self.view.showChatTree = True
        
        # 2. 执行切换会话
        self.view.switchSession("new-session-id")
        
        # 3. 验证状态是否已重置
        self.assertFalse(self.view.showSettings, "切换会话后设置面板应关闭")
        self.assertFalse(self.view.showConversationInstructions, "切换会话后指令弹窗应关闭")
        self.assertFalse(self.view.showChatTree, "切换会话后树状图应关闭")
        self.assertEqual(self.view.currentConversationId, "new-session-id")

    def test_start_new_chat_closes_all_ui(self):
        """测试开启新对话时是否关闭了所有 UI 覆盖层"""
        # 1. 模拟用户打开了设置面板
        self.view.showSettings = True
        
        # 2. 执行开启新对话
        self.view.startNewChat()
        
        # 3. 验证状态是否已重置
        self.assertFalse(self.view.showSettings, "开启新对话后设置面板应关闭")
        self.assertIsNone(self.view.currentConversationId)

if __name__ == "__main__":
    unittest.main()
