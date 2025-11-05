# 技术设计文档

OT Translator 实时翻译系统的技术架构与实现细节。

> 💡 **面向读者**：本文档面向开发者和系统维护者，包含详细的技术实现和扩展指南。  
> 如果你是用户，请参考 [USER_GUIDE.md](./USER_GUIDE.md) 获取配置和使用说明。

---

## 目录

1. [系统架构](#1-系统架构)
2. [核心特性实现](#2-核心特性实现)
   - [防抖机制](#21-防抖机制)
   - [同步显示模式](#22-同步显示模式)
   - [自适应批量翻译](#23-自适应批量翻译)
   - [增量渲染设计](#24-增量渲染设计)
3. [数据流设计](#3-数据流设计)
4. [性能优化](#4-性能优化)
5. [扩展开发指南](#5-扩展开发指南)

---

## 1. 系统架构

### 1.1 整体架构

```
┌─────────────────────────────────────────────────┐
│              User Voice Input                    │
└──────────────────┬──────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────┐
│          STT Provider (Deepgram/Azure)           │
│  - Streaming recognition                         │
│  - Interim & Final results                       │
└──────────────────┬──────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────┐
│           TranslationAgent (Backend)             │
│                                                  │
│  ┌──────────────┐      ┌──────────────┐         │
│  │  Debounced   │      │  Adaptive    │         │
│  │  Translator  │      │  Batch       │         │
│  │  (Interim)   │      │  Collector   │         │
│  └──────┬───────┘      └──────┬───────┘         │
│         │                     │                  │
│         └─────────┬───────────┘                  │
│                   ↓                              │
│        ┌──────────────────────┐                  │
│        │  Google Translate    │                  │
│        │  API                 │                  │
│        └──────────┬───────────┘                  │
│                   ↓                              │
│        ┌──────────────────────┐                  │
│        │  RPC Communication   │                  │
│        └──────────┬───────────┘                  │
└───────────────────┼──────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│            Frontend (React/Next.js)              │
│  - Real-time display                             │
│  - Delta-based fade-in animation                │
│  - Configuration UI                              │
└─────────────────────────────────────────────────┘
```

### 1.2 核心组件

| 组件 | 职责 | 文件位置 |
|------|------|---------|
| **TranslationAgent** | 主 Agent 类，协调所有翻译流程 | `translator_agent.py` |
| **DebouncedTranslator** | 处理 interim 翻译的防抖逻辑 | `translator_agent.py` |
| **AdaptiveBatchCollector** | 自适应批量收集器 | `translator_agent.py` |
| **BatchTranslator** | 批量翻译器 | `translator_agent.py` |
| **OrderedDispatcher** | 顺序分发器，确保结果按序发送 | `translator_agent.py` |

### 1.3 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| **STT** | Deepgram Nova-2/3, Azure Speech | 流式语音识别 |
| **翻译** | Google Cloud Translate API v2 | 机器翻译 |
| **后端框架** | LiveKit Agents SDK | Agent 框架 |
| **通信协议** | WebRTC DataChannel (SCTP) | 实时数据传输 |
| **RPC** | LiveKit RPC | 双向通信 |
| **前端框架** | Next.js 15 + React 19 | UI 框架 |
| **语言** | Python 3.9+, TypeScript 5+ | 编程语言 |

---

## 2. 核心特性实现

### 2.1 防抖机制

#### 设计目标
- 减少 API 调用次数，降低成本
- 保持实时响应性
- 避免翻译不完整的文本

#### 实现原理

```python
class DebouncedTranslator:
    def __init__(self, debounce_ms: float = 500, enabled: bool = True):
        self.debounce_delay = debounce_ms / 1000
        self.pending_task: Optional[asyncio.Task] = None
        self.translate_client = None
        self.enabled = enabled
    
    async def translate_debounced(
        self, 
        text: str,
        source_language: str,
        target_language: str,
        callback: Callable
    ):
        """
        防抖翻译：延迟执行，新请求会取消旧请求
        """
        # 1. 取消之前的待处理任务
        if self.pending_task and not self.pending_task.done():
            self.pending_task.cancel()
        
        # 2. 创建新的延迟任务
        async def delayed_translate():
            try:
                await asyncio.sleep(self.debounce_delay)
                result = await self._translate(text, source_language, target_language)
                await callback(result)
            except asyncio.CancelledError:
                logger.debug(f"Translation cancelled for: {text[:30]}...")
        
        # 3. 保存任务引用
        self.pending_task = asyncio.create_task(delayed_translate())
```

#### 工作流程

```
Time 0ms:   User says "Hello"
            ↓ [Interim]
            Trigger translation (Task A)
            Start 500ms timer
            
Time 200ms: User says "Hello wor"
            ↓ [Interim]
            Cancel Task A ✕
            Trigger translation (Task B)
            Start 500ms timer
            
Time 300ms: User says "Hello world"
            ↓ [Final]
            Cancel Task B ✕
            Immediate translation ✓ (no debounce)
            Send result to frontend
```

#### 优化效果

| 场景 | 无防抖 | 有防抖 (500ms) | 节省 |
|------|--------|---------------|------|
| 短句 (5 interim) | 6 次 API 调用 | 2 次 API 调用 | 67% |
| 长句 (10 interim) | 11 次 API 调用 | 2 次 API 调用 | 82% |

**关键设计**：
- ✅ Interim 结果使用防抖（可被取消）
- ✅ Final 结果立即翻译（不使用防抖）
- ✅ Final 到达时取消所有待处理的 interim 翻译

---

### 2.2 同步显示模式

#### 功能概述

两种实时显示模式，控制原文和译文的显示时机：

**模式 1：异步模式（默认）⚡**
- 行为：原文先显示，译文稍后显示
- 优点：响应速度快，用户能立即看到原文
- 适用场景：需要快速响应的实时字幕

**模式 2：同步模式 🔄**
- 行为：等译文准备好后，原文和译文一起发送
- 优点：视觉体验更整洁，避免"译文延迟"效果
- 适用场景：追求同步呈现的会议记录

#### 实现代码

```python
class TranslationAgent(Agent):
    def __init__(self, sync_display_mode: bool = False):
        self.sync_display_mode = sync_display_mode
    
    async def handle_stt_interim(self, text):
        if self.sync_display_mode:
            # 同步模式：等译文准备好后一起发送
            await self.translator.translate_sync(
                text=text,
                callback=lambda translated: self.send_both(text, translated)
            )
        else:
            # 异步模式：先发送原文
            await self.send_original(text)
            # 然后使用防抖翻译
            await self.translator.translate_debounced(
                text=text,
                callback=lambda translated: self.send_translation(translated)
            )
    
    async def handle_stt_final(self, text):
        # Final 结果的处理逻辑
        self.translator.cancel_pending_interim()  # 取消待处理的 interim
        
        if self.sync_display_mode:
            # 同步模式：等待翻译后一起发送
            translated = await self.translate_immediately(text)
            await self.send_both(text, translated, is_final=True)
        else:
            # 异步模式：立即发送原文
            await self.send_original(text, is_final=True)
            # 加入批量处理队列
            await self.batch_collector.add_sentence(text)
```

#### 数据流对比

**异步模式**：
```
STT Event → Send Original (t=0ms) → Frontend displays original
         ↓
    Debounce (t=500ms) → Translate → Send Translation → Frontend updates
```

**同步模式**：
```
STT Event → Translate (t=0-300ms) → Send Both (t=300ms) → Frontend displays both together
```

#### 配置方法

环境变量：
```bash
TRANSLATION_SYNC_DISPLAY_MODE=false  # 异步（默认）
TRANSLATION_SYNC_DISPLAY_MODE=true   # 同步
```

---

### 2.3 自适应批量翻译

#### 问题背景

**现象**：用户快速连续说话时，翻译显示越来越滞后

**原因**：
- 每个句子的翻译阻塞后续句子
- Google Translate API 单次调用 200-800ms
- 快速说话时延迟累积

**性能表现**：

| 场景 | 句子间隔 | 延迟表现 |
|------|---------|---------|
| 慢速说话 | > 1秒 | 稳定：~800ms/句 ✅ |
| 快速说话 | 0.3秒 | 累积：句1=0.8s, 句2=1.6s, 句3=2.4s ❌ |
| 极快说话 | 0.2秒 | 严重：句5延迟4秒+ ❌ |

#### 解决方案

**自适应批量翻译**：根据是否有积压，动态选择策略

```
新句子到达
    ↓
判断批次状态
    ↓
├─ 批次为空（无积压）
│  └─ 立即翻译（保持当前性能）✅
│     单句翻译：800ms
│
└─ 批次有句子（有积压）
   └─ 加入批次（利用批量API）
       ├─ 达到阈值 (3句) → 立即批量翻译
       └─ 未达到 → 超时 (500ms) 后批量翻译
           批量翻译3句：1200ms（平均400ms/句）
```

#### 核心代码

```python
class AdaptiveBatchCollector:
    def __init__(self, batch_size=3, batch_timeout_ms=500):
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout_ms / 1000
        self.pending_batch = []
        self.timeout_task = None
    
    async def add_sentence(self, sequence, text):
        # 🔑 关键判断：批次是否为空
        is_batch_empty = len(self.pending_batch) == 0
        
        self.pending_batch.append(PendingSentence(sequence, text))
        
        if is_batch_empty:
            # 情况1：批次为空，说明没有积压
            # → 立即翻译，不等待，保持原有性能
            await self._flush_batch()
        else:
            # 情况2：批次已有句子，说明有积压
            # → 利用批量优势
            if len(self.pending_batch) >= self.batch_size:
                # 达到批次大小，立即翻译
                await self._flush_batch()
            else:
                # 启动定时器，超时后批量翻译
                self._start_timer()
    
    async def _flush_batch(self):
        if not self.pending_batch:
            return
        
        # 取消超时定时器
        if self.timeout_task:
            self.timeout_task.cancel()
        
        # 批量翻译
        batch = self.pending_batch
        self.pending_batch = []
        
        await self.translate_callback(batch)
    
    def _start_timer(self):
        if self.timeout_task and not self.timeout_task.done():
            return  # 定时器已在运行
        
        async def timeout_handler():
            await asyncio.sleep(self.batch_timeout)
            await self._flush_batch()
        
        self.timeout_task = asyncio.create_task(timeout_handler())
```

#### 顺序保证

**问题**：批量翻译时，短句可能比长句先完成，导致顺序混乱

**解决**：OrderedDispatcher 确保按序发送

```python
class OrderedDispatcher:
    def __init__(self):
        self.next_sequence = 0  # 下一个应该发送的序号
        self.pending_results = {}  # {sequence: result}
    
    async def add_result(self, sequence, original, translated):
        """添加翻译结果，如果可以发送则立即发送"""
        self.pending_results[sequence] = (original, translated)
        
        # 按顺序发送所有可发送的结果
        while self.next_sequence in self.pending_results:
            result = self.pending_results.pop(self.next_sequence)
            await self.send_to_frontend(result)
            self.next_sequence += 1
```

**示例流程**：
```
句子到达顺序：#0, #1, #2
翻译完成顺序：#0, #2, #1（#2先完成）

Dispatcher 处理：
  #0 完成 → sequence=0 → 发送 ✓ (next=1)
  #2 完成 → sequence=2 → 等待 (next=1)
  #1 完成 → sequence=1 → 发送 #1 ✓ → 发送 #2 ✓ (next=3)
```

#### 性能提升

| 场景 | 无批量 | 有批量 | 提升 |
|------|--------|--------|------|
| 无堆积（慢速） | 800ms/句 | 800ms/句 | 0% (无回退✅) |
| 有堆积（快速3句） | 2400ms总 | 1600ms总 | 33% |
| 有堆积（快速5句） | 4000ms总 | 2000ms总 | 50% |

---

### 2.4 增量渲染设计

#### 问题描述

实时 ASR 系统（如 Deepgram）和机器翻译 API（如 Google Translate）会持续优化其输出结果。它们不仅仅是追加新内容——还经常修订之前转录或翻译的文本。

**例如**：
- ASR 可能会随着更多上下文的到来，将初步的误识别 "今天会意" 修正为正确的 "今天会议"
- 翻译可能会为了更好的流畅性而重新表达之前的词语

简单的"仅追加"方法会保留这些错误，造成糟糕的用户体验。

#### 解决方案架构

我们的实现使用 **full_text + delta** 方法：

##### 1. 数据结构

```typescript
{
  type: 'interim' | 'final',
  original: {
    full_text: string,    // 完整的当前文本
    delta: string,        // 新增/修改的部分
    language: string
  },
  translation: {
    full_text: string,    // 完整的译文
    delta: string,        // 新增/修改的部分
    language: string
  }
}
```

##### 2. 后端逻辑 - Delta 计算

**算法：最长公共前缀（Longest Common Prefix）**

```python
def compute_delta(prev_text: str, current_text: str) -> str:
    """
    计算两个文本的差异（delta）
    
    Examples:
        compute_delta("Hello", "Hello world")  → " world"
        compute_delta("今天会意", "今天会议很重要") → "议很重要"
    """
    if not prev_text:
        return current_text
    
    if not current_text:
        return ""
    
    # 找到最长公共前缀
    common_prefix_len = 0
    min_len = min(len(prev_text), len(current_text))
    
    while common_prefix_len < min_len and prev_text[common_prefix_len] == current_text[common_prefix_len]:
        common_prefix_len += 1
    
    # 返回当前文本中新增或修改的部分
    delta = current_text[common_prefix_len:]
    return delta
```

**为什么使用最长公共前缀而不是复杂的 diff 算法？**
- ✅ 实时 STT 通常是追加式更新，偶尔修正
- ✅ 计算复杂度 O(n)，性能优秀
- ✅ 足够处理 99% 的场景

**Delta 计算示例**：

```python
# 示例 1：纯追加
prev = "今天会意"       # [0=今, 1=天, 2=会, 3=意]
curr = "今天会议很重要"  # [0=今, 1=天, 2=会, 3=议, 4=很, 5=重, 6=要]

# 比较过程：
#   索引 0: "今" == "今" ✅
#   索引 1: "天" == "天" ✅
#   索引 2: "会" == "会" ✅
#   索引 3: "意" != "议" ❌ (停止)

common_prefix_len = 3
delta = curr[3:] = "议很重要"
```

##### 3. 前端渲染策略

**显示逻辑**：
```typescript
function updateDisplay(data: TranslationData) {
  // 1. 使用 full_text 作为真实内容（确保正确性）
  setText(data.original.full_text);
  
  // 2. 使用 delta 驱动动画效果
  if (data.original.delta) {
    animateNewContent(data.original.delta);
  }
}
```

**前端 Delta 检测（用于动画）**：

```typescript
const computeTextChanges = (oldText: string, newText: string): TextChange[] => {
  const changes: TextChange[] = [];
  
  // 找到相同的前缀
  let commonPrefixLength = 0;
  const minLength = Math.min(oldText.length, newText.length);
  while (commonPrefixLength < minLength && 
         oldText[commonPrefixLength] === newText[commonPrefixLength]) {
    commonPrefixLength++;
  }
  
  // 找到相同的后缀（处理中间修改的情况）
  let commonSuffixLength = 0;
  const maxSuffixLength = minLength - commonPrefixLength;
  while (
    commonSuffixLength < maxSuffixLength &&
    oldText[oldText.length - 1 - commonSuffixLength] === 
    newText[newText.length - 1 - commonSuffixLength]
  ) {
    commonSuffixLength++;
  }
  
  // 相同的前缀部分（无动画）
  if (commonPrefixLength > 0) {
    changes.push({
      type: 'same',
      text: newText.slice(0, commonPrefixLength),
    });
  }
  
  // 中间变化的部分（带淡入动画）
  const newMiddle = newText.slice(
    commonPrefixLength, 
    newText.length - commonSuffixLength
  );
  if (newMiddle) {
    changes.push({
      type: 'modified',
      text: newMiddle,
    });
  }
  
  // 相同的后缀部分（无动画）
  if (commonSuffixLength > 0) {
    changes.push({
      type: 'same',
      text: newText.slice(newText.length - commonSuffixLength),
    });
  }
  
  return changes;
};
```

##### 4. 示例流程

```
时间 1（临时）：
  full_text: "今天会意"
  delta: "今天会意"
  → UI 显示："今天会意"（带淡入效果）

时间 2（临时）：
  full_text: "今天会议很重要"
  delta: "议很重要"
  → UI 更新："今天会议很重要"
  → "意" 修正为 "议"，"很重要" 淡入

时间 3（最终）：
  full_text: "今天会议很重要请准时参加"
  delta: "请准时参加"
  → 历史记录："今天会议很重要请准时参加"
  → 清除临时状态
```

##### 5. 优势

- ✅ 通过 delta 动画实现流畅的淡入视觉效果
- ✅ 当 ASR/翻译修订文本时自动纠正
- ✅ 避免仅追加方法累积的错误
- ✅ 适用于任何实时 ASR/翻译提供商
- ✅ 前后端职责分离：后端计算 delta，前端渲染动画

---

## 3. 数据流设计

### 3.1 Interim 事件流

```
STT Interim Event
    ↓
[1] 判断显示模式
    ├─ 异步模式 → 立即发送原文到前端
    │              ↓
    │           [2] 判断是否启用防抖
    │              ├─ 已启用 → DebouncedTranslator
    │              │              ↓
    │              │           等待 500ms
    │              │              ↓
    │              │           取消检查（Final到达则取消）
    │              │              ↓
    │              │           调用 Google Translate API
    │              │              ↓
    │              │           发送译文到前端
    │              │
    │              └─ 未启用 → 立即翻译
    │                             ↓
    │                          发送译文到前端
    │
    └─ 同步模式 → 等待翻译完成
                   ↓
                原文和译文一起发送到前端
```

### 3.2 Final 事件流

```
STT Final Event
    ↓
[1] 取消待处理的 Interim 翻译任务
    ↓
[2] 判断显示模式
    ├─ 异步模式 → 立即发送原文
    │              ↓
    │           AdaptiveBatchCollector.add_sentence()
    │              ↓
    │           判断批次状态
    │              ├─ 批次为空 → 立即翻译
    │              │              ↓
    │              │           直接发送到前端
    │              │
    │              └─ 批次不为空 → 加入批次
    │                              ↓
    │                           达到阈值或超时
    │                              ↓
    │                           批量翻译
    │                              ↓
    │                           OrderedDispatcher.add_result()
    │                              ↓
    │                           按序发送译文到前端
    │
    └─ 同步模式 → 等待翻译完成
                   ↓
                原文和译文一起发送到前端
```

### 3.3 RPC 通信协议

**后端 → 前端**（翻译更新）:
```typescript
{
  type: 'interim' | 'final',
  original: {
    full_text: string,  // 完整当前文本
    delta: string,      // 新增/修改部分
    language: string
  },
  translation: {
    full_text: string,
    delta: string,
    language: string
  }
}
```

**前端 → 后端**（配置更新）:
```typescript
{
  sourceLanguage: string,   // 'en', 'zh', etc.
  targetLanguage: string,
  debounceMs: number,       // 100-1000
  syncDisplayMode?: boolean // 可选
}
```

---

## 4. 性能优化

### 4.1 API 调用优化

**策略组合**：

1. **防抖（Debounce）**：减少 interim 翻译
   - 节省：60-80% API 调用
   - 实现：延迟执行 + 任务取消

2. **批量（Batch）**：合并 final 翻译
   - 节省：30-50% 总延迟（有堆积时）
   - 实现：自适应批量收集器

3. **取消（Cancel）**：Final 到达时取消 interim
   - 节省：额外 10-20% API 调用
   - 实现：任务引用 + asyncio.cancel()

4. **缓存（Cache）**：相同文本复用结果（可选）
   - 节省：5-10% API 调用（重复场景）
   - 实现：LRU Cache

### 4.2 内存管理

```python
# 限制批次大小
MAX_BATCH_SIZE = 10

# 限制等待队列
MAX_PENDING_RESULTS = 50

# 定期清理过期任务
async def cleanup_expired_tasks():
    current_time = time.time()
    expired = [
        seq for seq, (text, ts) in self.pending.items()
        if current_time - ts > 60  # 超过60秒
    ]
    for seq in expired:
        del self.pending[seq]
```

### 4.3 性能基准

**测试环境**：
- 网络：50ms RTT
- STT：Deepgram Nova-2
- 翻译：Google Translate API v2

**结果**：

| 指标 | 值 |
|------|---|
| Interim 显示延迟 | 50-100ms |
| Interim 翻译延迟 | 550-600ms (含防抖) |
| Final 翻译延迟 | 200-300ms |
| 批量翻译延迟 | 300-500ms (3句) |

---

## 5. 扩展开发指南

### 5.1 添加新的 STT 提供商

1. 在 `TranslationAgent.__init__()` 中添加配置
2. 更新环境变量文档
3. 测试 interim 和 final 事件

```python
# 示例：添加 AssemblyAI 支持
if stt_provider == "assemblyai":
    from livekit.plugins import assemblyai
    stt = assemblyai.STT(
        language=source_language,
        interim_results=True
    )
```

### 5.2 添加新的翻译服务

```python
class CustomTranslator:
    async def translate(self, text, source_lang, target_lang):
        # 实现自定义翻译逻辑
        # 例如：调用 DeepL API
        pass

# 在 TranslationAgent 中使用
self.custom_translator = CustomTranslator()
```

### 5.3 自定义防抖策略

```python
class AdaptiveDebouncer(DebouncedTranslator):
    async def translate_debounced(self, text, ...):
        # 根据文本长度动态调整防抖时间
        if len(text) < 20:
            self.debounce_delay = 0.2  # 短文本快速翻译
        elif len(text) > 100:
            self.debounce_delay = 1.0  # 长文本延迟翻译
        else:
            self.debounce_delay = 0.5  # 默认
        
        await super().translate_debounced(text, ...)
```

### 5.4 监控和指标

```python
class MetricsCollector:
    def __init__(self):
        self.api_calls = 0
        self.total_latency = 0
        self.cache_hits = 0
    
    def record_translation(self, latency_ms):
        self.api_calls += 1
        self.total_latency += latency_ms
    
    def get_stats(self):
        return {
            'api_calls': self.api_calls,
            'avg_latency': self.total_latency / self.api_calls,
            'cache_hit_rate': self.cache_hits / self.api_calls
        }

# 集成到 TranslationAgent
self.metrics = MetricsCollector()
```

### 5.5 测试工具

```python
# 模拟 STT 事件
async def simulate_speech(agent, sentences):
    for sentence in sentences:
        # 模拟 interim 更新
        for i in range(1, len(sentence), 5):
            await agent.handle_interim(sentence[:i])
            await asyncio.sleep(0.1)
        
        # 发送 final
        await agent.handle_final(sentence)
        await asyncio.sleep(0.5)

# 使用
await simulate_speech(agent, [
    "Hello world",
    "How are you today",
    "I am doing great"
])
```

### 5.6 自定义 Delta 计算

如果需要更复杂的 diff 算法：

```python
import difflib

def compute_delta_advanced(prev_text: str, current_text: str) -> str:
    """使用 difflib 进行更精确的 diff 计算"""
    sm = difflib.SequenceMatcher(None, prev_text, current_text)
    
    # 获取所有操作
    opcodes = sm.get_opcodes()
    
    # 提取新增和修改的部分
    delta_parts = []
    for tag, i1, i2, j1, j2 in opcodes:
        if tag in ('insert', 'replace'):
            delta_parts.append(current_text[j1:j2])
    
    return ''.join(delta_parts)
```

---

## 附录

### A. 关键配置参数

| 参数 | 默认值 | 建议范围 | 说明 |
|------|--------|---------|------|
| `debounce_ms` | 500 | 100-1000 | 防抖延迟 |
| `batch_size` | 3 | 2-5 | 批量大小 |
| `batch_timeout_ms` | 500 | 200-1000 | 批量超时 |
| `sync_display_mode` | false | - | 显示模式 |
| `DEEPGRAM_ENDPOINTING_MS` | 1000 | 500-2500 | Deepgram 断句静音时长 |
| `AZURE_SEGMENTATION_SILENCE_MS` | 1500 | 500-2500 | Azure 断句静音时长 |

### B. 常见问题（技术向）

**Q: 为什么批量翻译只用于 Final？**
A: Interim 需要实时响应，批量会增加延迟。Final 可以容忍小延迟，且有堆积时批量更高效。

**Q: Delta 计算为什么不用复杂的 diff 算法？**
A: 实时 STT 通常是追加式更新，最长公共前缀足够且更快（O(n) vs O(n²)）。

**Q: 如何选择 debounce_ms？**
A: 
- 快速响应：100-300ms
- 平衡：400-600ms
- 节省成本：700-1000ms

**Q: OrderedDispatcher 是否会无限增长？**
A: 有内存限制和超时清理机制，pending_results 最多保留 50 条，超过 60 秒自动清理。

**Q: 能否支持更多并发用户？**
A: 可以，每个用户是独立的 Agent 实例。需要注意：
- Google Cloud API 配额限制
- 服务器内存和 CPU 资源
- LiveKit 房间数限制

---

**文档版本**: v2.0  
**最后更新**: 2025-11-04  
**作者**: Translation System Team  
**相关文档**: [README.md](./README.md) | [USER_GUIDE.md](./USER_GUIDE.md)
