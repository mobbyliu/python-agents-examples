# 同步显示模式功能实现总结

## 功能概述

为OT Translator实时翻译系统添加了一个显示模式开关，允许用户选择两种不同的实时显示方式：

### 模式1：异步模式（默认）⚡
- **行为**：原文先显示，译文稍后显示
- **优点**：响应速度快，用户能立即看到原文
- **适用场景**：需要快速响应的场合

### 模式2：同步模式 🔄
- **行为**：服务端等译文准备好后，原文和译文一起发送并显示
- **优点**：视觉体验更整洁，避免"译文延迟"效果
- **适用场景**：追求同步呈现效果的场合

## 实现的改动

### 1. 后端改动 (deepgram_translator_agent.py)

#### 1.1 DebouncedTranslator类
- 添加了 `sync_mode` 参数和配置
- 新增 `update_sync_mode()` 方法用于动态更新模式
- 新增 `translate_sync()` 方法实现同步模式翻译

```python
class DebouncedTranslator:
    def __init__(self, debounce_ms: float = 500, enabled: bool = True, sync_mode: bool = False):
        self.sync_mode = sync_mode  # 新增
        ...
    
    async def translate_sync(self, text, source_language, target_language, callback):
        """同步模式翻译：等待翻译完成后，原文和译文一起发送"""
        ...
```

#### 1.2 DeepgramTranslationAgent类
- 构造函数添加 `sync_display_mode` 参数
- `update_config()` 方法支持更新 `sync_display_mode`
- `stt_node()` 方法中根据模式选择不同的处理逻辑：
  - 异步模式：先发送原文，然后使用 `translate_debounced()`
  - 同步模式：使用 `translate_sync()` 等待译文完成后一起发送

```python
if self.sync_display_mode:
    # 同步模式：等译文准备好后，原文和译文一起发送
    await self.translator.translate_sync(...)
else:
    # 异步模式：先发送原文到前端
    await self.send_translation_to_frontend(...)
    # 使用防抖机制翻译
    await self.translator.translate_debounced(...)
```

#### 1.3 entrypoint函数
- 添加环境变量 `TRANSLATION_SYNC_DISPLAY_MODE` 的读取
- RPC配置更新接口支持 `syncDisplayMode` 参数

### 2. 前端改动 (session-view.tsx)

#### 配置说明更新
- 在配置面板的提示文字中说明显示模式由后端环境变量控制
- 前端不提供UI切换功能，保持配置的一致性和简洁性

### 3. 文档更新

#### 3.1 env.template
添加了新的环境变量配置说明：
```bash
# TRANSLATION_SYNC_DISPLAY_MODE=false  # false: show original first, then translation (faster); true: show both together (sync)
```

#### 3.2 README.md
添加了新的"Display Modes"章节，详细说明：
- 两种模式的行为和优势
- 配置方法（环境变量和UI）
- 视觉对比示例

## 使用方法

### 通过环境变量配置
在 `.env` 文件中设置：
```bash
TRANSLATION_SYNC_DISPLAY_MODE=false  # 或 true
```

重启 agent 使设置生效。

## 技术细节

### 数据流程

**异步模式 (sync_display_mode=false):**
```
STT interim event → 
  ↓
Backend: send_translation_to_frontend(original, translation=None) →
  ↓
Frontend: 显示原文 →
  ↓
Backend: translate_debounced() → wait → translate →
  ↓
Backend: send_translation_to_frontend(original, translation) →
  ↓
Frontend: 更新显示译文
```

**同步模式 (sync_display_mode=true):**
```
STT interim event → 
  ↓
Backend: translate_sync() → wait → translate →
  ↓
Backend: send_translation_to_frontend(original, translation) →
  ↓
Frontend: 原文和译文一起显示
```

### 兼容性
- ✅ 向后兼容：默认使用异步模式（原有行为）
- ✅ 环境变量配置：通过后端环境变量统一管理

## 测试建议

### 测试场景1：异步模式（默认）
1. 设置 `TRANSLATION_SYNC_DISPLAY_MODE=false` 或不设置
2. 启动 agent
3. 开始说话
4. 观察：原文应该立即出现，译文稍后出现

### 测试场景2：同步模式
1. 设置 `TRANSLATION_SYNC_DISPLAY_MODE=true`
2. 重启 agent
3. 开始说话
4. 观察：原文和译文应该同时出现（有轻微延迟）

## 文件清单

修改的文件：
1. `/translators/ot-translator/deepgram_translator_agent.py` - 后端逻辑
2. `/translators/ot-translator/ot-translator-frontend/components/session-view.tsx` - 前端UI
3. `/env.template` - 环境变量模板
4. `/translators/ot-translator/README.md` - 文档

新增的文件：
1. `/translators/ot-translator/SYNC_DISPLAY_MODE_FEATURE.md` - 本文档

## 总结

该功能为用户提供了更多的控制选项，可以根据不同的使用场景选择最合适的显示模式：
- **异步模式**：适合需要快速响应的实时字幕场景
- **同步模式**：适合需要整洁呈现的会议记录场景

实现简洁、无侵入性，完全向后兼容，可以无缝集成到现有系统中。

