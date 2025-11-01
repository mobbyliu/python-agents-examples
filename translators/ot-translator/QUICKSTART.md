# 🚀 快速启动指南

## 5 分钟快速开始使用 Deepgram + Google Translate 翻译系统

### 前置准备（一次性）

#### 1. 设置 Google Cloud 认证

**方式 A：简单方式（推荐用于开发/测试）**

只需要 3 个命令，无需下载 JSON 文件：

```bash
# 1. 安装 gcloud CLI（如果还没有）
# macOS: brew install google-cloud-sdk
# 或访问: https://cloud.google.com/sdk/docs/install

# 2. 登录你的 Google 账号
gcloud auth application-default login

# 3. 设置项目并启用 API
gcloud config set project YOUR_PROJECT_ID
gcloud services enable translate.googleapis.com
```

完成！现在可以直接使用，不需要设置 `GOOGLE_APPLICATION_CREDENTIALS` 环境变量。

**方式 B：生产方式（使用 Service Account JSON）**

适合生产环境或 CI/CD：

```bash
# 1. 访问 https://console.cloud.google.com/
# 2. 创建或选择项目
# 3. 启用 Cloud Translation API
# 4. 创建 Service Account (角色: Cloud Translation API User)
# 5. 下载 JSON key 文件到本地
# 6. 设置环境变量: GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
```

#### 2. 获取 Deepgram API Key

```bash
# 访问 https://console.deepgram.com/
# 创建账号并获取 API Key
```

### 快速启动（3 步）

#### 步骤 1：安装依赖（30 秒）

```bash
cd /Users/mobby/code/python-agents-examples
pip install google-cloud-translate>=3.0.0
```

#### 步骤 2：配置环境变量（1 分钟）

编辑 `.env` 文件（如果不存在，从 `.env.template` 复制）：

```bash
# 必需配置
LIVEKIT_URL=your_livekit_url
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret
DEEPGRAM_API_KEY=your_deepgram_api_key

# Google Cloud 配置 - 方式 A（gcloud login）无需设置
# Google Cloud 配置 - 方式 B（Service Account）需要设置：
# GOOGLE_APPLICATION_CREDENTIALS=/path/to/your-service-account-key.json
# GOOGLE_CLOUD_PROJECT=your_project_id

# 可选：默认配置
TRANSLATION_SOURCE_LANGUAGE=en
TRANSLATION_TARGET_LANGUAGE=zh
TRANSLATION_DEBOUNCE_MS=500
```

> 💡 **提示**：如果使用 `gcloud auth application-default login`（方式 A），无需设置 `GOOGLE_APPLICATION_CREDENTIALS`

#### 步骤 3：启动（1 分钟）

**终端 1 - 启动后端**：
```bash
python translators/ot-translator/deepgram_translator_agent.py dev
```

看到这个消息说明成功：
```
✅ Google Cloud Translate client initialized successfully
✅ DeepgramTranslationAgent initialized: en -> zh, debounce=500ms
```

**终端 2 - 启动前端**：
```bash
cd translators/ot-translator/ot-translator-frontend
pnpm install  # 首次运行需要
pnpm dev
```

访问 http://localhost:3000

### 使用（2 分钟）

1. **连接**：点击 "Connect" 按钮，允许麦克风权限
2. **配置**：点击 ⚙️ 配置 → 选择源语言和目标语言 → 保存
3. **开始说话**：对着麦克风说话，实时查看翻译结果

### 验证安装

运行此命令验证 Google Cloud 配置：

```bash
python3 -c "from google.cloud import translate_v2; client = translate_v2.Client(); print('✅ 配置成功')"
```

### 常见启动问题

#### 问题 1：`Failed to initialize Google Translate client`
```bash
# 检查环境变量
echo $GOOGLE_APPLICATION_CREDENTIALS
# 确保文件存在
ls -l $GOOGLE_APPLICATION_CREDENTIALS
```

#### 问题 2：`Deepgram authentication failed`
```bash
# 检查 API key
echo $DEEPGRAM_API_KEY
```

#### 问题 3：前端无法连接
```bash
# 检查 LiveKit 配置
echo $LIVEKIT_URL
```

### 下一步

- 📖 详细文档：查看 `DEEPGRAM_README.md`
- ✅ 测试指南：查看 `TESTING.md`
- 📝 实现总结：查看 `IMPLEMENTATION_SUMMARY.md`

### 快速命令参考

```bash
# 启动 Deepgram 版本
python translators/ot-translator/deepgram_translator_agent.py dev

# 启动 Gladia 版本（原版本）
python translators/ot-translator/agent.py dev

# 启动前端
cd translators/ot-translator/ot-translator-frontend && pnpm dev

# 验证配置
python3 -c "from google.cloud import translate_v2; translate_v2.Client()"

# 检查语法
python3 -m py_compile translators/ot-translator/deepgram_translator_agent.py
```

### 支持的语言

| 代码 | 语言 | 代码 | 语言 |
|------|------|------|------|
| en   | 英语 | zh   | 中文 |
| fr   | 法语 | es   | 西班牙语 |
| de   | 德语 | ja   | 日语 |
| ko   | 韩语 | pt   | 葡萄牙语 |
| ru   | 俄语 | ar   | 阿拉伯语 |

（完整列表见 [Google Translate 语言支持](https://cloud.google.com/translate/docs/languages)）

### 成功！ 🎉

现在你可以：
- 用任何支持的语言说话
- 实时看到翻译结果
- 在前端 UI 切换语言对
- 调整防抖延迟优化性能

---

**遇到问题？** 查看完整的故障排查指南：`DEEPGRAM_README.md` 第 284-329 行

