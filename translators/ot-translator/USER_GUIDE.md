# 用户指南：OT Translator 实时翻译系统

完整的安装、配置和使用指南。

---

## 目录

1. [快速开始（5分钟）](#快速开始5分钟)
2. [详细配置](#详细配置)
3. [使用说明](#使用说明)
4. [测试指南](#测试指南)
5. [故障排查](#故障排查)
6. [API 成本估算](#api-成本估算)

---

## 快速开始（5分钟）

### 方式 A：使用 gcloud CLI（推荐）

最简单的方式，只需 3 个命令：

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

完成！无需下载 JSON 文件或设置环境变量。

### 方式 B：使用 Service Account（生产环境）

适合生产环境或 CI/CD，请参考[详细配置](#详细配置)章节。

### 启动系统（3步）

**步骤 1：安装依赖**（30秒）
```bash
pip install -r requirements.txt
```

**步骤 2：配置环境变量**（1分钟）

编辑 `.env` 文件：
```bash
# 必需配置
LIVEKIT_URL=your_livekit_url
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret
DEEPGRAM_API_KEY=your_deepgram_api_key

# 可选：STT 提供商（默认 deepgram）
STT_PROVIDER=deepgram  # 或 "azure"

# Google Cloud - 方式A 无需配置
# Google Cloud - 方式B 需要配置：
# GOOGLE_APPLICATION_CREDENTIALS=/path/to/your-key.json
```

**步骤 3：启动**（1分钟）

终端 1 - 后端：
```bash
python translators/ot-translator/translator_agent.py dev
```

终端 2 - 前端：
```bash
cd translators/ot-translator/ot-translator-frontend
pnpm install  # 首次运行需要
pnpm dev
```

访问 http://localhost:3000 → 点击配置 → 选择语言 → 开始说话！

---

## 详细配置

### 1. Google Cloud 项目设置

#### 步骤 1：创建项目

1. 访问 [Google Cloud Console](https://console.cloud.google.com/)
2. 创建新项目或选择现有项目
3. 记录项目 ID

#### 步骤 2：启用 Cloud Translation API

1. 导航到 **APIs & Services > Library**
2. 搜索 "Cloud Translation API"
3. 点击 "Enable"

#### 步骤 3：创建 Service Account（方式B）

1. 导航到 **IAM & Admin > Service Accounts**
2. 点击 **Create Service Account**
3. 填写名称（如：`translation-service`）
4. 授予角色：**Cloud Translation API User**
5. 点击 **Continue** 和 **Done**

#### 步骤 4：下载 Service Account Key（方式B）

1. 点击刚创建的 Service Account
2. 进入 **Keys** 标签
3. 点击 **Add Key > Create new key**
4. 选择 **JSON** 格式
5. 保存文件到安全位置（如：`~/google-cloud-credentials.json`）

#### 验证配置

```bash
python3 -c "from google.cloud import translate_v2; client = translate_v2.Client(); print('✅ Google Translate API 配置成功')"
```

---

### 2. STT 提供商配置

系统支持两种 STT 提供商，根据你的需求选择：

| 提供商 | 最适用场景 | 中文准确率 | 多语言检测 |
|--------|-----------|-----------|-----------|
| **Deepgram** | 英文为主的内容 | 良好 | 有限（Nova-2） |
| **Azure Speech** | 中文为主的内容 | 优秀 | 原生流式支持 |

#### 选项 A：Deepgram（默认）

1. 访问 [Deepgram Console](https://console.deepgram.com/)
2. 创建账户或登录
3. 获取 API Key
4. 在 `.env` 中配置：

```bash
STT_PROVIDER=deepgram
DEEPGRAM_API_KEY=your_deepgram_api_key
```

#### 选项 B：Azure Speech

1. 访问 [Azure Portal](https://portal.azure.com/)
2. 创建 "Speech" 资源
3. 记录 **Subscription Key** 和 **Region**
4. 在 `.env` 中配置：

```bash
STT_PROVIDER=azure
AZURE_SPEECH_KEY=your_azure_speech_key
AZURE_SPEECH_REGION=eastus  # 或你的区域
```

**推荐使用 Azure Speech 的场景**：
- 中文语音识别为主
- 需要更高的中文识别准确率
- 使用双向翻译模式（中英文自动切换）

---

### 3. 环境变量完整配置

复制 `.env.template` 到 `.env`：

```bash
# ═══════════════════════════════════════════════
# LiveKit Configuration
# ═══════════════════════════════════════════════
LIVEKIT_URL=your_livekit_url
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret

# ═══════════════════════════════════════════════
# STT Provider Selection
# ═══════════════════════════════════════════════
STT_PROVIDER=deepgram  # 或 "azure"

# Deepgram Configuration（使用 Deepgram 时）
DEEPGRAM_API_KEY=your_deepgram_api_key

# Azure Speech Configuration（使用 Azure 时）
# AZURE_SPEECH_KEY=your_azure_speech_key
# AZURE_SPEECH_REGION=eastus

# ═══════════════════════════════════════════════
# Google Cloud Translation
# ═══════════════════════════════════════════════
# 方式A（gcloud CLI）：无需配置
# 方式B（Service Account）：
# GOOGLE_APPLICATION_CREDENTIALS=/path/to/your-key.json
# GOOGLE_CLOUD_PROJECT=your_project_id

# ═══════════════════════════════════════════════
# Translation Configuration（可选）
# ═══════════════════════════════════════════════
TRANSLATION_SOURCE_LANGUAGE=en
TRANSLATION_TARGET_LANGUAGE=zh
TRANSLATION_DEBOUNCE_MS=500
TRANSLATION_BIDIRECTIONAL_MODE=false  # true=双向翻译（中英互译）
TRANSLATION_SYNC_DISPLAY_MODE=false   # true=同步显示模式

# STT Endpointing Configuration（句子长度控制）
# ═══════════════════════════════════════════════
DEEPGRAM_ENDPOINTING_MS=1000          # Deepgram 断句静音时长（默认1000ms）
AZURE_SEGMENTATION_SILENCE_MS=1500   # Azure 断句静音时长（默认1500ms）
```

#### 配置说明

**STT_PROVIDER**：
- `deepgram`（默认）：适合英文为主的内容
- `azure`：适合中文为主或中英混合的内容

**TRANSLATION_DEBOUNCE_MS**（防抖延迟）：
- `100-300ms`：快速响应，但 API 调用较多
- `500ms`（推荐）：平衡速度和成本
- `700-1000ms`：节省成本，但延迟较高

**TRANSLATION_BIDIRECTIONAL_MODE**（双向翻译）：
- `false`（默认）：单向翻译（源语言 → 目标语言）
- `true`：自动检测中文/英文，翻译为另一种语言

**TRANSLATION_SYNC_DISPLAY_MODE**（显示模式）：
- `false`（默认）：异步模式 - 原文立即显示，译文稍后显示
- `true`：同步模式 - 等待翻译完成后，原文和译文一起显示

**DEEPGRAM_ENDPOINTING_MS / AZURE_SEGMENTATION_SILENCE_MS**（句子长度控制）：
> 💡 **这是控制句子长度的关键参数**

这个参数决定了 STT 引擎在多长时间的静音后会结束当前句子（断句）。

- **较小的值（500-1000ms）**：
  - ✅ 句子更短，更频繁
  - ✅ 响应更快
  - ❌ 可能打断完整语义
  - 适用场景：实时字幕、快速对话

- **较大的值（1500-2500ms）**：
  - ✅ 句子更长，更完整
  - ✅ 更好的语义完整性
  - ❌ 响应稍慢
  - 适用场景：会议记录、演讲翻译

**默认值说明**：
- `DEEPGRAM_ENDPOINTING_MS=1000`：Deepgram 默认较激进，适合快速对话
- `AZURE_SEGMENTATION_SILENCE_MS=1500`：Azure 默认较保守，适合完整语句

**调整建议**：
```bash
# 如果觉得 Deepgram 句子太短，增大 endpointing 值
DEEPGRAM_ENDPOINTING_MS=1500

# 如果觉得 Azure 句子太长，减小 segmentation 值
AZURE_SEGMENTATION_SILENCE_MS=1000
```

---

## 使用说明

### 1. 连接到房间

1. 启动后端和前端
2. 在前端界面点击 "Connect"
3. Agent 自动加入房间并准备接收语音

### 2. 配置翻译语言

1. 点击原文区域标题栏的 **⚙️ 配置** 按钮
2. 在配置面板中选择：
   - **源语言**：你要说话的语言（如：英语）
   - **目标语言**：翻译目标语言（如：中文）
3. 点击 **保存配置**

配置会自动：
- 💾 保存到浏览器 localStorage（持久化）
- 📡 通过 RPC 发送到后端
- ⚡ 立即生效

**💡 提示**：防抖延迟和显示模式需要通过后端环境变量配置（见[详细配置](#详细配置)章节）

### 3. 开始说话

1. 允许浏览器使用麦克风权限
2. 开始说话
3. 观察实时效果：

**交替显示模式**：
- **实时预览卡片**（虚线边框）：显示正在识别的原文和译文（临时状态）
- **历史对话气泡**：已确认的对话记录，带淡入动画

**分屏显示模式**：
- **原文区域**（上半屏）：直接显示原文，带淡入动画
- **译文区域**（下半屏）：直接显示译文，带淡入动画

### 4. 动画效果

- 新增内容会自动带有淡入动画（基于 delta 计算）
- 修正的内容会平滑更新
- 无需手动配置

---

## 测试指南

### 完整测试流程

#### 测试 1：基础翻译

**步骤**：
1. 说话：`"Hello world"`
2. **交替显示模式**：观察实时预览卡片（虚线框）显示原文和译文，完成后转为历史对话气泡
3. **分屏显示模式**：观察原文和译文直接在各自区域显示
4. 观察译文延迟 500ms 后出现（防抖机制）

**预期后端日志**：
```
[INTERIM] Original (en): Hello wor...
[FINAL] Original (en): Hello world
Translated (en -> zh): Hello world -> 你好世界
```

---

#### 测试 2：防抖机制

**目的**：验证防抖功能正常工作

**步骤**：
1. 打开配置，调整防抖延迟到 **1000ms**
2. 说一个长句子：`"This is a long sentence to test the debounce mechanism"`
3. 观察实时输入快速更新，但译文延迟 1 秒后才出现

**验证要点**：
- ✅ 原文实时更新（无延迟）
- ✅ 译文延迟 1 秒后出现
- ✅ 减少了中间状态的翻译次数（节省成本）

---

#### 测试 3：语言切换

**步骤**：
1. 打开配置面板
2. 源语言选择：**中文 (Chinese)**
3. 目标语言选择：**英语 (English)**
4. 保存配置
5. 说话：`"你好，今天天气很好"`

**预期结果**：
- 译文显示：`"Hello, the weather is nice today"`

**预期后端日志**：
```
Config updated successfully
INFO:translator:TranslationAgent initialized: zh -> en, debounce=500ms
```

---

#### 测试 4：压力测试

**步骤**：
快速连续说 5 句短句，中间几乎不停顿：
1. "Hello"
2. "How are you"
3. "I am fine"
4. "Thank you"
5. "Goodbye"

**验证**：
- ✅ 所有句子都被正确识别
- ✅ 翻译结果按顺序显示（不混乱）
- ✅ 无丢失或重复

---

### 测试检查清单

**后端功能**：
- [ ] Agent 成功启动
- [ ] Google Translate 客户端初始化成功
- [ ] STT 连接成功（Deepgram 或 Azure）
- [ ] RPC 方法注册成功
- [ ] 接收前端配置更新

**前端功能**：
- [ ] 成功连接到房间
- [ ] 配置界面正常显示
- [ ] 语言选择器工作正常
- [ ] 配置保存到 localStorage

**翻译功能**：
- [ ] 临时文本实时显示
- [ ] 最终文本正确显示
- [ ] 翻译结果正确
- [ ] 防抖机制生效
- [ ] 多句话顺序正确
- [ ] 语言切换正常

**UI/UX**：
- [ ] 淡入动画流畅
- [ ] 自动滚动正常
- [ ] 两种显示模式（交替/分屏）切换正常
- [ ] 响应式布局正常

---

### 性能指标

**预期延迟**：
- **临时结果显示**：< 100ms
- **临时结果翻译**：防抖延迟 + 200ms
- **最终结果翻译**：< 300ms
- **淡入动画**：CSS transition 300ms

**API 调用频率**：
- **STT**：连续流式连接
- **Google Translate**：
  - 临时结果：每 防抖延迟 一次（可能被取消）
  - 最终结果：每句话一次

---

## 故障排查

### 1. Google Translate API 错误

**错误信息**：`Failed to initialize Google Translate client`

**解决方案**：

**方式A（gcloud CLI）**：
```bash
# 重新登录
gcloud auth application-default login

# 确认项目设置
gcloud config get-value project

# 确认 API 已启用
gcloud services list --enabled | grep translate
```

**方式B（Service Account）**：
- ✅ 检查 `GOOGLE_APPLICATION_CREDENTIALS` 路径是否正确
- ✅ 确保 JSON 文件存在且可读
- ✅ 验证 Cloud Translation API 已启用
- ✅ 确认 Service Account 有 "Cloud Translation API User" 角色

---

### 2. Deepgram 连接失败

**错误信息**：`Deepgram authentication failed`

**解决方案**：
- ✅ 检查 `DEEPGRAM_API_KEY` 是否正确
- ✅ 确认账户有足够的额度
- ✅ 访问 [Deepgram Console](https://console.deepgram.com/) 查看使用情况
- ✅ 确认没有超出 API 限制

---

### 3. Azure Speech STT 配置错误

**错误信息**：`Failed to initialize Azure Speech STT`

**解决方案**：
- ✅ 检查 `AZURE_SPEECH_KEY` 是否正确
- ✅ 确认 `AZURE_SPEECH_REGION` 与 Azure 资源区域一致（如：eastus, westus2）
- ✅ 验证 Azure Speech 服务已创建且处于活动状态
- ✅ 检查 `STT_PROVIDER` 环境变量是否设置为 `azure`
- ✅ 确保已安装 Azure 插件：`pip install livekit-agents[azure]`

---

### 4. RPC 配置无法更新

**症状**：前端更改语言配置后没有效果

**解决方案**：
- ✅ 确保 Agent 已连接（查看后端日志）
- ✅ 检查浏览器控制台是否有 RPC 错误
- ✅ 尝试刷新页面重新连接
- ✅ 检查后端日志是否有 `Config updated` 消息

---

### 5. 翻译延迟过高

**症状**：译文显示明显滞后

**解决方案**：
- 🚀 降低防抖延迟到 100-300ms
- 🌐 检查网络连接速度
- 📍 确认 Google Cloud 项目区域设置
- 🔄 尝试切换到异步显示模式（`TRANSLATION_SYNC_DISPLAY_MODE=false`）

---

### 6. Azure 双向翻译语言检测问题

**症状**：使用 Azure STT 时，语言检测不准确或翻译方向错误

**解决方案**：
- ✅ 确认 `TRANSLATION_BIDIRECTIONAL_MODE=true` 已设置
- ✅ 检查日志中的语言检测信息：
  ```
  🔍 [Azure STT] Detected language: zh-CN for text: '...'
  🔍 [LANGUAGE DETECTION] Detected source language: 'zh'
  ✅ [TRANSLATION DIRECTION] zh -> en
  ```
- 💡 Azure STT 提供初步检测，Google Translate 提供最终确认（双重检测机制）

---

### 7. 麦克风权限问题

**症状**：前端无法获取语音输入

**解决方案**：
- 🎤 确保浏览器允许麦克风权限
- 🔒 HTTPS 环境下才能访问麦克风（localhost 例外）
- 🔄 尝试刷新页面并重新授权
- 🔧 检查操作系统的麦克风设置

---

## API 成本估算

### Google Cloud Translate Pricing

- **文本翻译**：$20 / 百万字符
- **每月免费额度**：50 万字符

### STT 提供商定价

#### Deepgram Pricing

- **实时 STT**：
  - Nova-2：$0.0043 / 分钟
  - Nova-3：$0.0059 / 分钟
- **每月免费额度**：$200 额度

#### Azure Speech Pricing

- **实时 STT**：$1.00 / 小时（标准版）
- **每月免费额度**：5 小时音频转录

---

### 示例计算

**假设条件**：
- 平均说话速度：150 词/分钟
- 平均词长：5 字符
- 防抖延迟：500ms
- 每句话临时更新：5 次

**1 小时使用成本**：

| 服务 | 计算 | 成本 |
|------|------|------|
| Deepgram STT | 60 分钟 × $0.0043 | **$0.26** |
| Google Translate（最终） | 60 × 150 × 5 = 45,000 字符 | $0.0009 |
| Google Translate（临时） | ~9,000 字符（防抖减少 80%） | $0.0002 |
| **总计** | | **~$0.26/小时** |

**使用 Azure Speech**：

| 服务 | 计算 | 成本 |
|------|------|------|
| Azure Speech | 1 小时 × $1.00 | **$1.00** |
| Google Translate | 54,000 字符 | $0.001 |
| **总计** | | **~$1.00/小时** |

---

### 成本优化建议

1. **调整防抖延迟**
   - 500ms：节省 ~60% API 调用
   - 1000ms：节省 ~80% API 调用

2. **禁用临时翻译**
   - 仅翻译最终结果
   - 节省 ~15% 总成本

3. **批量处理**
   - 系统已自动启用
   - 快速说话时节省 30-50% 延迟

4. **选择合适的 STT 提供商**
   - 英文为主：Deepgram（成本更低）
   - 中文为主：Azure（准确率更高，但成本略高）

5. **设置使用配额限制**
   - 在 Google Cloud Console 设置每日配额
   - 避免意外超支

---

## 语言支持

系统支持 Google Translate API 的所有语言（100+ 种）。

### 常用语言

| 代码 | 语言 | 代码 | 语言 |
|------|------|------|------|
| en   | 英语 | zh   | 中文 |
| fr   | 法语 | es   | 西班牙语 |
| de   | 德语 | ja   | 日语 |
| ko   | 韩语 | pt   | 葡萄牙语 |
| ru   | 俄语 | ar   | 阿拉伯语 |
| hi   | 印地语 | it   | 意大利语 |

**完整语言列表**：[Google Cloud Translate 支持的语言](https://cloud.google.com/translate/docs/languages)

### 添加新语言

1. 在前端 `components/split-view-display.tsx` 中添加到 `SUPPORTED_LANGUAGES`：
```typescript
{ code: 'hi', name: '印地语 (Hindi)' },
```

2. 无需修改后端代码（Google Translate 自动支持）

---

## 开发者提示

**需要深入了解技术实现？**

请参考 **[DESIGN.md](./DESIGN.md)** 技术设计文档，包含：
- 系统架构设计
- 防抖机制实现原理
- 自适应批量翻译算法
- 增量渲染（delta 计算）
- 性能优化策略
- 扩展开发指南

---

**文档版本**: v2.0  
**最后更新**: 2025-11-04  
**维护者**: Translation System Team
