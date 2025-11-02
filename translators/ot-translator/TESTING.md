# Deepgram + Google Translate 翻译系统测试指南

## 前置准备

### 1. 安装依赖
```bash
# 在项目根目录
pip install google-cloud-translate>=3.0.0
```

### 2. 验证 Google Cloud 配置
```bash
# 测试 Google Translate API 是否可用
python3 -c "from google.cloud import translate_v2; client = translate_v2.Client(); print('✅ Google Translate API 配置成功')"
```

如果失败，检查：
- `GOOGLE_APPLICATION_CREDENTIALS` 环境变量是否正确
- Service Account JSON 文件是否存在
- Cloud Translation API 是否已启用

### 3. 验证 Deepgram API Key
```bash
# 检查环境变量
echo $DEEPGRAM_API_KEY
```

### 4. （可选）配置译文防抖开关

要禁用译文防抖，可在启动前设置环境变量：

```bash
export TRANSLATION_DEBOUNCE_ENABLED=false
```

默认值为 `true`，表示启用防抖机制。关闭后，译文将在每次识别更新时立即返回，有助于调试实时回显问题。

## 测试步骤

### 步骤 1：启动后端 Agent

```bash
cd /Users/mobby/code/python-agents-examples
python translators/ot-translator/deepgram_translator_agent.py dev
```

**预期输出**：
```
INFO:deepgram-translator:Google Cloud Translate client initialized successfully
INFO:deepgram-translator:DeepgramTranslationAgent initialized: en -> zh, debounce_ms=500.0, debounce_enabled=True
```

**常见错误**：
- `Failed to initialize Google Translate client` → 检查 Google Cloud 配置
- `Deepgram authentication failed` → 检查 DEEPGRAM_API_KEY

### 步骤 2：启动前端

```bash
cd translators/ot-translator/ot-translator-frontend
pnpm install  # 首次运行
pnpm dev
```

访问 http://localhost:3000

### 步骤 3：连接测试

1. 点击 "Connect" 按钮
2. 允许麦克风权限
3. 观察控制台是否有错误

**预期**：
- Agent 成功连接到房间
- 前端显示 "Connected" 状态

### 步骤 4：配置语言测试

1. 点击原文区域标题栏的 **⚙️ 配置** 按钮
2. 选择源语言：英语 (English)
3. 选择目标语言：中文 (Chinese)
4. 防抖延迟：500ms
5. 点击 **保存配置**

**验证**：
- 后端日志显示：`Config updated successfully`
- 前端控制台显示：`Config updated successfully`
- 配置面板自动关闭

### 步骤 5：基础翻译测试

**测试用例 1：简单英文句子**

1. 说话：`"Hello world"`
2. 观察原文区域：
   - 实时输入框（虚线）显示 `"Hello wor..."` (interim)
   - 最终文本显示 `"Hello world"` (final，带打字机效果)
3. 观察译文区域：
   - 延迟 500ms 后显示 `"你好世界"` (interim)
   - Final 确认后重新显示（打字机效果）

**预期后端日志**：
```
[INTERIM] Original (en): Hello wor...
[FINAL] Original (en): Hello world
Translated (en -> zh): Hello world -> 你好世界
```

**测试用例 2：多句连续**

1. 说话：`"Good morning"`
2. 暂停 2 秒
3. 说话：`"How are you"`
4. 观察两句话分别显示，中间有换行

### 步骤 6：防抖机制测试

1. 打开配置，调整防抖延迟到 **1000ms**
2. 保存配置
3. 说一个长句子：`"This is a long sentence to test the debounce mechanism"`
4. 观察：
   - Interim 文本快速更新（原文）
   - 译文延迟 1 秒后才出现
   - 减少了中间状态的翻译次数

### 步骤 7：语言切换测试

**测试用例：中文到英文**

1. 打开配置
2. 源语言：中文 (Chinese)
3. 目标语言：英语 (English)
4. 保存
5. 说话：`"你好，今天天气很好"`
6. 观察译文：`"Hello, the weather is nice today"`

### 步骤 8：打字机效果测试

1. 点击译文区域的 **逐字** / **逐词** 按钮
2. 说话并观察效果差异：
   - 逐字：一个字符一个字符显示
   - 逐词：一个词一个词显示

### 步骤 9：实时输入开关测试

1. 取消勾选 **实时输入** 复选框
2. 说话
3. 观察：不再显示虚线框的 interim 文本
4. 只显示 final 结果

### 步骤 10：压力测试

**快速连续说话**：
1. 快速说 5 句短句，中间几乎不停顿
2. 观察：
   - 所有句子都被正确识别
   - 翻译结果按顺序显示
   - 无丢失或混乱

## 测试检查清单

### 后端功能
- [ ] Agent 成功启动
- [ ] Google Translate 客户端初始化成功
- [ ] Deepgram STT 连接成功
- [ ] RPC 方法注册成功
- [ ] 接收前端配置更新

### 前端功能
- [ ] 成功连接到房间
- [ ] 配置界面正常显示
- [ ] 语言选择器工作正常
- [ ] 防抖滑块工作正常
- [ ] 配置保存到 localStorage
- [ ] RPC 配置发送成功

### 翻译功能
- [ ] Interim 文本实时显示
- [ ] Final 文本正确显示
- [ ] 翻译结果正确
- [ ] 防抖机制生效
- [ ] 多句话顺序正确
- [ ] 语言切换正常

### UI/UX
- [ ] 打字机效果流畅
- [ ] 自动滚动正常
- [ ] 实时输入开关生效
- [ ] 逐字/逐词切换正常
- [ ] 响应式布局正常

## 常见问题排查

### 问题 1：翻译结果不正确

**可能原因**：
- 源语言设置错误
- Deepgram 识别错误

**排查**：
1. 检查配置的源语言是否匹配你的说话语言
2. 查看后端日志的 `[FINAL]` 输出，确认识别文本是否正确

### 问题 2：译文延迟过高

**可能原因**：
- 防抖延迟设置过高
- 网络延迟

**排查**：
1. 降低防抖延迟到 100-300ms
2. 检查网络连接
3. 查看后端日志的时间戳

### 问题 3：配置更新无效

**可能原因**：
- RPC 通信失败
- Agent 未正确注册 RPC 方法

**排查**：
1. 查看浏览器控制台错误
2. 查看后端日志是否有 `Config updated` 消息
3. 尝试刷新页面重新连接

### 问题 4：前端不显示翻译

**可能原因**：
- RPC 方法未注册
- 数据格式错误

**排查**：
1. 打开浏览器开发者工具 > Console
2. 查看是否有 RPC 错误
3. 检查后端是否成功发送数据（查看日志）

## 性能指标

### 预期延迟
- **Interim 显示延迟**：< 100ms
- **Interim 翻译延迟**：debounce_ms + 200ms
- **Final 翻译延迟**：< 300ms
- **打字机效果延迟**：根据模式（30ms/字符 或 100ms/词）

### API 调用频率
- **Deepgram**：连续流式连接
- **Google Translate**：
  - Interim：每 debounce_ms 一次（可能被取消）
  - Final：每句话一次

## 成功标准

系统通过测试的标准：
1. ✅ 所有测试用例通过
2. ✅ 无控制台错误
3. ✅ 翻译准确率 > 95%
4. ✅ 实时性良好（延迟 < 1秒）
5. ✅ 配置切换正常
6. ✅ 长时间运行稳定（10+ 分钟）

## 下一步

测试通过后，可以：
1. 调整默认配置（语言、防抖时间）
2. 添加更多语言到前端选择器
3. 部署到生产环境
4. 监控 API 使用量和成本

## 报告问题

如果发现 bug，请记录：
- 重现步骤
- 预期行为 vs 实际行为
- 后端日志
- 前端控制台输出
- 配置信息（源语言、目标语言、防抖延迟）

