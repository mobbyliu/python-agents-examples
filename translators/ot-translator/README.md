# OT Translator：实时翻译系统

基于多提供商 STT（Deepgram 或 Azure Speech）和 Google Cloud Translate API 的实时流式翻译系统。

## ✨ 核心特点

- **实时转录**：支持 Deepgram 或 Azure Speech，可灵活切换
- **流式翻译**：Google Cloud Translate API，支持 100+ 种语言
- **智能优化**：防抖机制 + 自适应批量翻译，降低成本、减少延迟
- **动态配置**：前端 UI 实时切换源语言和目标语言
- **双向翻译**：自动检测语言方向（中英文互译）

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

创建 `.env` 文件：

```bash
# LiveKit 配置
LIVEKIT_URL=your_livekit_url
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret

# STT 提供商选择（可选，默认 deepgram）
STT_PROVIDER=deepgram  # 或 "azure"

# Deepgram 配置
DEEPGRAM_API_KEY=your_deepgram_api_key

# 或者 Azure Speech 配置
# AZURE_SPEECH_KEY=your_azure_speech_key
# AZURE_SPEECH_REGION=eastus

# Google Cloud 配置（方式1：gcloud CLI）
# 运行: gcloud auth application-default login
# 或者（方式2：Service Account）
# GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
```

### 3. 启动系统

**后端**：
```bash
python translators/ot-translator/translator_agent.py dev
```

**前端**：
```bash
cd translators/ot-translator/ot-translator-frontend
pnpm install  # 首次运行
pnpm dev
```

**访问**: http://localhost:3000

## 🎯 STT 提供商选择

| 提供商 | 最适用场景 | 中文准确率 | 多语言检测 |
|--------|-----------|-----------|-----------|
| **Deepgram** | 英文为主的内容 | 良好 | 有限（Nova-2） |
| **Azure Speech** | 中文为主的内容 | 优秀 | 原生流式支持 |

**配置方式**：设置环境变量 `STT_PROVIDER=deepgram` 或 `azure`

## 📖 使用说明

1. 在浏览器中打开前端界面
2. 连接到 LiveKit 房间
3. 点击配置按钮 ⚙️，选择源语言和目标语言
4. 开始说话，观察实时翻译效果

**💡 提示**：防抖延迟和显示模式通过后端环境变量配置（详见 [USER_GUIDE.md](./USER_GUIDE.md)）

## 🏗️ 工作原理

```
用户语音
  ↓
STT（Deepgram/Azure）→ 实时转录
  ↓
防抖机制 → 减少 API 调用
  ↓
Google Translate → 流式翻译
  ↓
LiveKit RPC → WebRTC 传输
  ↓
前端显示（淡入动画）
```

**核心技术**：
- **防抖优化**：临时结果延迟翻译，最终结果立即翻译
- **批量处理**：快速说话时自动合并翻译，减少延迟
- **增量渲染**：使用 delta 算法实现流畅的文本更新动画

## 💰 成本估算

**1 小时使用成本**（假设中速说话）：
- Deepgram STT: ~$0.26
- Google Translate: ~$0.001
- **总计**: ~$0.26/小时

**优化建议**：调整防抖延迟（500-1000ms）可节省 60-80% 的 API 调用。

## 📚 文档导航

**开始使用？**
- 👉 **[USER_GUIDE.md](./USER_GUIDE.md)** - 完整用户指南
  - 详细安装步骤（Google Cloud + STT 配置）
  - 使用教程
  - 测试指南
  - 故障排查
  - API 成本详解

**了解技术实现？**
- 👉 **[DESIGN.md](./DESIGN.md)** - 技术设计文档
  - 系统架构设计
  - 核心算法实现（防抖、批量翻译、增量渲染）
  - 性能优化策略
  - 扩展开发指南

**前端开发？**
- 👉 **[ot-translator-frontend/README.md](./ot-translator-frontend/README.md)** - 前端项目说明

## 🔧 常见问题

**Q: 翻译延迟太高？**
A: 降低防抖延迟到 100-300ms，或检查网络连接。

**Q: 中文识别不准？**
A: 切换到 Azure Speech（`STT_PROVIDER=azure`），中文准确率更高。

**Q: Deepgram 句子太短？ Azure 句子太长？**
A: 这是因为两个 STT 提供商的**断句机制（endpointing）**不同：
- **Deepgram**：默认 1000ms 静音后断句（较激进）
- **Azure**：默认 1500ms 静音后断句（较保守）

**解决方案**：在 `.env` 中调整断句时长：
```bash
# 如果 Deepgram 句子太短，增大值
DEEPGRAM_ENDPOINTING_MS=1500

# 如果 Azure 句子太长，减小值
AZURE_SEGMENTATION_SILENCE_MS=1000
```

**Q: Google Cloud 认证失败？**
A: 运行 `gcloud auth application-default login` 或检查 `GOOGLE_APPLICATION_CREDENTIALS` 路径。

详细故障排查请参考 [USER_GUIDE.md](./USER_GUIDE.md#故障排查)。

---

**项目状态**: ✅ 生产就绪  
**支持语言**: 100+ 种（Google Translate 支持的所有语言）  
**许可证**: 与主项目相同
