<template>
  <div class="openclaw-settings">
    <h2>OpenClaw 连接配置</h2>

    <el-card class="box-card">
      <template #header>
        <div class="card-header">
          <span>配置列表</span>
          <el-button type="primary" @click="handleAdd">新增配置</el-button>
        </div>
      </template>
      <el-table :data="configs" style="width: 100%">
        <el-table-column prop="display_name" label="显示名称" />
        <el-table-column prop="gateway_url" label="网关地址" />
        <el-table-column prop="use_ssh" label="SSH" width="80">
          <template #default="scope">
            <el-tag :type="scope.row.use_ssh ? 'success' : 'info'">{{ scope.row.use_ssh ? '是' : '否' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200">
          <template #default="scope">
            <el-button size="small" @click="handleEdit(scope.row)">编辑</el-button>
            <el-popconfirm
              title="确定删除此配置吗？"
              @confirm="handleDelete(scope.row.id)"
            >
              <template #reference>
                <el-button size="small" type="danger">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑配置' : '新增配置'" width="50%">
      <el-form :model="form" label-width="120px" ref="formRef">
        <el-form-item label="显示名称" prop="displayName" required>
          <el-input v-model="form.displayName" />
        </el-form-item>
        <el-form-item label="网关地址" prop="gatewayUrl" required>
          <el-input v-model="form.gatewayUrl" placeholder="例如 ws://127.0.0.1:18789" />
        </el-form-item>
        <el-form-item label="会话 Key" prop="sessionKey" required>
          <el-input v-model="form.sessionKey" placeholder="例如 agent:main:main" />
        </el-form-item>
        <el-form-item label="网关 Token" prop="gatewayToken">
          <el-input v-model="form.gatewayToken" type="password" show-password />
        </el-form-item>
        <el-form-item label="网关密码" prop="gatewayPassword">
          <el-input v-model="form.gatewayPassword" type="password" show-password />
        </el-form-item>
        
        <el-divider />

        <el-form-item label="使用 SSH 隧道" prop="useSsh">
          <el-switch v-model="form.useSsh" />
        </el-form-item>

        <template v-if="form.useSsh">
          <el-form-item label="SSH 主机" prop="sshHost" required>
            <el-input v-model="form.sshHost" />
          </el-form-item>
          <el-form-item label="SSH 端口" prop="sshPort" required>
            <el-input-number v-model="form.sshPort" :min="1" :max="65535" />
          </el-form-item>
          <el-form-item label="SSH 用户名" prop="sshUser" required>
            <el-input v-model="form.sshUser" />
          </el-form-item>
          <el-form-item label="SSH 密码" prop="sshPassword" required>
            <el-input v-model="form.sshPassword" type="password" show-password />
          </el-form-item>
          <el-form-item label="本地隧道端口" prop="sshLocalPort">
            <el-input-number v-model="form.sshLocalPort" :min="0" :max="65535" />
            <div class="form-tip">0 表示随机分配端口</div>
          </el-form-item>
        </template>

      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleSubmit">
            {{ isEdit ? '保存' : '创建' }}
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import { 
  getOpenClawConfigs, 
  createOpenClawConfig, 
  updateOpenClawConfig, 
  deleteOpenClawConfig 
} from '@/api/openclaw';
import { useUserStore } from '@/stores/userStore';

const userStore = useUserStore();
const configs = ref([]);
const dialogVisible = ref(false);
const isEdit = ref(false);
const form = ref({});
const formRef = ref(null);

const resetForm = () => {
  form.value = {
    displayName: '',
    gatewayUrl: '',
    sessionKey: 'agent:main:main',
    gatewayToken: '',
    gatewayPassword: '',
    useSsh: false,
    sshHost: '',
    sshPort: 22,
    sshUser: '',
    sshPassword: '',
    sshLocalPort: 0,
  };
};

const loadConfigs = async () => {
  try {
    const response = await getOpenClawConfigs(userStore.userInfo.id);
    configs.value = response.data;
  } catch (error) {
    ElMessage.error('加载 OpenClaw 配置失败');
    console.error(error);
  }
};

const handleAdd = () => {
  resetForm();
  isEdit.value = false;
  dialogVisible.value = true;
};

const handleEdit = (row) => {
  form.value = {
    id: row.id,
    displayName: row.display_name,
    gatewayUrl: row.gateway_url,
    sessionKey: row.session_key,
    gatewayToken: row.gateway_token,
    gatewayPassword: row.gateway_password,
    useSsh: row.use_ssh,
    sshHost: row.ssh_host,
    sshPort: row.ssh_port,
    sshUser: row.ssh_user,
    sshPassword: row.ssh_password,
    sshLocalPort: row.ssh_local_port,
  };
  isEdit.value = true;
  dialogVisible.value = true;
};

const handleDelete = async (id) => {
  try {
    await deleteOpenClawConfig(id, userStore.userInfo.id);
    ElMessage.success('删除成功');
    await loadConfigs();
  } catch (error) {
    ElMessage.error('删除失败');
    console.error(error);
  }
};

const handleSubmit = async () => {
  if (!formRef.value) return;
  await formRef.value.validate(async (valid) => {
    if (valid) {
      try {
        const payload = {
          display_name: form.value.displayName,
          gateway_url: form.value.gatewayUrl,
          session_key: form.value.sessionKey,
          gateway_token: form.value.gatewayToken,
          gateway_password: form.value.gatewayPassword,
          use_ssh: form.value.useSsh,
          ssh_host: form.value.sshHost,
          ssh_port: form.value.sshPort,
          ssh_user: form.value.sshUser,
          ssh_password: form.value.sshPassword,
          ssh_local_port: form.value.sshLocalPort,
          user_id: userStore.userInfo.id
        };
        if (isEdit.value) {
          await updateOpenClawConfig(form.value.id, payload);
          ElMessage.success('更新成功');
        } else {
          await createOpenClawConfig(payload);
          ElMessage.success('创建成功');
        }
        dialogVisible.value = false;
        await loadConfigs();
      } catch (error) {
        ElMessage.error(isEdit.value ? '更新失败' : '创建失败');
        console.error(error);
      }
    }
  });
};

onMounted(() => {
  loadConfigs();
});
</script>

<style scoped>
.openclaw-settings {
  padding: 20px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.form-tip {
  color: #909399;
  font-size: 12px;
  margin-left: 10px;
}
</style>
