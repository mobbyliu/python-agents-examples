# Deepgram + Google Translate 实时翻译系统

基于 Deepgram STT 和 Google Cloud Translate API 的实时流式翻译系统，支持多语言配置和智能防抖优化。

## 功能特点

- **实时语音识别**：使用 Deepgram STT 进行高质量语音转文字
- **流式翻译**：Google Cloud Translate API v2 (Basic) 实时翻译
- **智能防抖**：对 interim results 使用可配置的防抖机制，减少 API 调用
- **语言灵活配置**：
  - 支持 10+ 种语言（英语、中文、法语、西班牙语、德语等）
  - 前端 UI 实时切换源语言和目标语言
  - 配置保存到 localStorage，持久化
- **实时更新界面**：
  - Interim results 实时显示（虚线框）
  - Final results 带打字机效果
  - 自动纠偏和确认

## 系统架构

```
用户语音 
  ↓
Deepgram STT (interim + final)
  ↓
防抖队列 (仅 interim, 可配置延迟)
  ↓
Google Cloud Translate API
  ↓
RPC 通信 (WebRTC DataChannel)
  ↓
前端显示 (打字机效果)
```

## 前置条件

### 1. Google Cloud 项目设置

#### 步骤 1：创建 Google Cloud 项目

1. 访问 [Google Cloud Console](https://console.cloud.google.com/)
2. 创建新项目或选择现有项目
3. 记录下项目 ID

#### 步骤 2：启用 Cloud Translation API

1. 在 Google Cloud Console 中，导航到 **APIs & Services > Library**
2. 搜索 "Cloud Translation API"
3. 点击 "Enable" 启用 API

#### 步骤 3：创建 Service Account

1. 导航到 **IAM & Admin > Service Accounts**
2. 点击 **Create Service Account**
3. 填写名称（例如：`translation-service`）
4. 点击 **Create and Continue**
5. 授予角色：**Cloud Translation API User**
6. 点击 **Continue** 和 **Done**

#### 步骤 4：下载 Service Account Key

1. 在 Service Accounts 列表中，点击刚创建的账户
2. 进入 **Keys** 标签
3. 点击 **Add Key > Create new key**
4. 选择 **JSON** 格式
5. 保存下载的 JSON 文件到安全位置（例如：`~/google-cloud-credentials.json`）

### 2. Deepgram API Key

1. 访问 [Deepgram Console](https://console.deepgram.com/)
2. 创建账户或登录
3. 获取 API Key

## 安装和配置

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

这会安装：
- `google-cloud-translate>=3.0.0`
- `livekit-agents[deepgram]`
- 其他必要依赖

### 2. 配置环境变量

复制 `.env.template` 到 `.env` 并填写以下变量：

```bash
# LiveKit Configuration
LIVEKIT_URL=your_livekit_url
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret

# Deepgram Configuration
DEEPGRAM_API_KEY=your_deepgram_api_key

# Google Cloud Translation Configuration
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/service-account-key.json
GOOGLE_CLOUD_PROJECT=your_project_id

# Optional: Translation Defaults
TRANSLATION_SOURCE_LANGUAGE=en
TRANSLATION_TARGET_LANGUAGE=zh
TRANSLATION_DEBOUNCE_MS=500
```

**重要**：确保 `GOOGLE_APPLICATION_CREDENTIALS` 指向你下载的 Service Account JSON 文件的绝对路径。

### 3. 验证配置

测试 Google Cloud 凭证是否有效：

```bash
python3 -c "from google.cloud import translate_v2; client = translate_v2.Client(); print('✅ Google Translate API 配置成功')"
```

如果成功，你会看到成功消息。如果失败，检查：
- `GOOGLE_APPLICATION_CREDENTIALS` 路径是否正确
- Service Account 是否有正确的权限
- Cloud Translation API 是否已启用

## 运行应用

### 启动后端 Agent

使用 Deepgram + Google Translate 版本：

```bash
python translators/ot-translator/deepgram_translator_agent.py dev
```

### 启动前端

```bash
cd translators/ot-translator/ot-translator-frontend
pnpm install  # 首次运行时
pnpm dev
```

访问 http://localhost:3000

## 使用说明

### 1. 连接到房间

1. 在前端界面点击 "Connect" 连接到 LiveKit 房间
2. Agent 会自动加入并准备好接收语音输入

### 2. 配置翻译语言

1. 点击原文区域标题栏的 **⚙️ 配置** 按钮
2. 选择：
   - **源语言**：你要说话的语言（例如：英语）
   - **目标语言**：你希望翻译成的语言（例如：中文）
   - **防抖延迟**：调整滑块（100ms - 1000ms）
     - 更快（100ms）：更实时，但 API 调用更多
     - 更稳（1000ms）：更省 API 调用，但延迟更高
3. 点击 **保存配置**

配置会：
- 保存到浏览器 localStorage（持久化）
- 通过 RPC 发送到后端 Agent
- 立即生效

### 3. 开始说话

1. 允许浏览器使用麦克风
2. 开始说话
3. 观察实时效果：
   - **实时输入区域**（虚线框）：显示正在识别的文本（interim）
   - **原文区域**：最终确认的文本带打字机效果
   - **译文区域**：翻译结果带打字机效果

### 4. 调整显示效果

- **实时输入开关**：控制是否显示 interim results
- **逐字/逐词按钮**：切换打字机效果模式
  - 逐字：较慢，戏剧性强（适合演示）
  - 逐词：较快，更流畅（适合实用）

## 工作原理

### 防抖机制

为了优化性能和减少 API 调用成本，系统对 interim results 使用防抖机制：

```python
# 伪代码
async def handle_interim_text(text):
    # 取消之前的待处理翻译
    if pending_translation_task:
        pending_translation_task.cancel()
    
    # 延迟 debounce_ms 后再翻译
    pending_translation_task = asyncio.create_task(
        delayed_translate(text, debounce_ms)
    )

async def handle_final_text(text):
    # Final 结果立即翻译，不使用防抖
    translation = await translate_immediately(text)
    send_to_frontend(text, translation, is_final=True)
```

**优势**：
- 减少不必要的 API 调用（用户说话中途的不完整文本）
- 降低成本（Google Translate API 按字符收费）
- 仍然保持实时性（用户看到原文更新）

### 事件流程

1. **用户说话** → Deepgram 开始识别
2. **Interim Event 1** → 原文显示：`"Hello"`
3. **Interim Event 2** → 原文更新：`"Hello wor"`
4. **Interim Event 3** → 原文更新：`"Hello world"`
   - 防抖：等待 500ms
   - 如果没有新的 interim，调用翻译 API
   - 译文显示：`"你好世界"`（interim 状态）
5. **Final Event** → 原文确认：`"Hello world"`
   - 立即翻译（不等待）
   - 译文确认：`"你好世界"`（final 状态，打字机效果）

## 语言支持

当前支持的语言（可在代码中扩展）：

| 代码 | 语言 | 
|------|------|
| en   | 英语 |
| zh   | 中文 |
| fr   | 法语 |
| es   | 西班牙语 |
| de   | 德语 |
| ja   | 日语 |
| ko   | 韩语 |
| pt   | 葡萄牙语 |
| ru   | 俄语 |
| ar   | 阿拉伯语 |

完整的语言列表见 [Google Cloud Translate 支持的语言](https://cloud.google.com/translate/docs/languages)。

## 与 Gladia 版本的对比

| 特性 | Gladia 版本 (`agent.py`) | Deepgram 版本 (`deepgram_translator_agent.py`) |
|------|-------------------------|-----------------------------------------------|
| STT 提供商 | Gladia | Deepgram |
| 翻译服务 | Gladia 内置 | Google Cloud Translate |
| 语言配置 | 代码写死 | 前端 UI 动态配置 |
| 防抖优化 | 无 | 有（可配置） |
| 成本 | Gladia 统一定价 | STT + Translation 分开计费 |
| 语言支持 | 有限 | 100+ 语言（Google Translate） |
| 实时性 | 高 | 高（with 防抖） |

**建议**：
- **Gladia 版本**：适合快速原型，all-in-one 解决方案
- **Deepgram 版本**：适合生产环境，更灵活，成本可控

## 故障排查

### 1. Google Translate API 错误

**错误信息**：`Failed to initialize Google Translate client`

**解决方案**：
- 检查 `GOOGLE_APPLICATION_CREDENTIALS` 路径是否正确
- 确保 Service Account JSON 文件存在且可读
- 验证 Cloud Translation API 已启用
- 确认 Service Account 有 "Cloud Translation API User" 角色

### 2. Deepgram 连接失败

**错误信息**：`Deepgram authentication failed`

**解决方案**：
- 检查 `DEEPGRAM_API_KEY` 是否正确
- 确认账户有足够的额度
- 查看 [Deepgram 控制台](https://console.deepgram.com/) 的使用情况

### 3. RPC 配置无法更新

**症状**：前端更改语言配置后没有效果

**解决方案**：
- 确保 Agent 已连接（查看后端日志）
- 检查浏览器控制台是否有 RPC 错误
- 尝试刷新页面重新连接

### 4. 翻译延迟过高

**解决方案**：
- 降低防抖延迟（100-300ms）
- 检查网络连接
- 确认 Google Cloud 项目的区域设置

## API 调用成本估算

### Google Cloud Translate Pricing

- 文本翻译：$20 / 百万字符
- 每月免费额度：50 万字符

### Deepgram Pricing

- 实时 STT：$0.0043 / 分钟（Nova-2 模型）
- 每月免费额度：200 美元

### 示例计算

假设：
- 平均说话速度：150 词/分钟
- 平均词长：5 字符
- 防抖延迟：500ms
- 每句话 interim 更新：5 次

**1 小时使用成本**：
- Deepgram：60 分钟 × $0.0043 = **$0.26**
- Google Translate：
  - Final translations：60 × 150 × 5 = 45,000 字符
  - Interim translations（with 500ms 防抖）：约 9,000 字符
  - 总计：54,000 字符 × $20 / 1,000,000 = **$0.001**
- **总计：约 $0.26 / 小时**

**成本优化建议**：
- 增加防抖延迟（减少 interim 翻译）
- 仅翻译 final results（关闭 interim 翻译）
- 设置使用配额限制

## 开发指南

### 添加新语言

1. 在前端 `split-view-display.tsx` 中添加到 `SUPPORTED_LANGUAGES`：
```typescript
{ code: 'hi', name: '印地语 (Hindi)' },
```

2. 无需修改后端代码（Google Translate 自动支持）

### 自定义防抖逻辑

修改 `deepgram_translator_agent.py` 中的 `DebouncedTranslator` 类：

```python
# 例如：根据文本长度动态调整防抖
async def translate_debounced(self, text, ...):
    # 短文本：更快翻译
    if len(text) < 20:
        self.debounce_delay = 0.2
    else:
        self.debounce_delay = 0.5
    # ... 继续原有逻辑
```

### 监控和日志

后端日志级别：
```python
logger.setLevel(logging.DEBUG)  # 更详细的日志
```

关键日志：
- `[INTERIM]`：实时转录
- `[FINAL]`：最终转录
- `Translated`：翻译完成
- `Config updated`：配置更新

## 贡献

欢迎提交 PR 和 Issue！

## 许可

与主项目相同。

