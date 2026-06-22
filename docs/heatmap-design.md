# DeepSeek 30日消费热力图 — 设计方案

> 状态：设计中，尚未实现
> 目标设备：MindReset Quote/0 e-ink (296×152)

## 概述

为 Quote/0 设备设计一个独立的 GitHub 风格热力图视图，展示近 30 天 DeepSeek API 每日消费情况。该视图与现有的余额仪表盘（DeepSeek Balance）完全独立，通过 `--heatmap` 标志单独推送。

## 屏幕布局设计

```
┌──────────────────────────────────────────────┐
│  近30日消费                  05.24 — 06.22   │  ← 标题行, 16px
│                                              │
│       5/24  5/31  6/7   6/14  6/21          │  ← 每周起始日期, 10px
│   一   ■     □     □     ■     ■     ■       │
│   二   □     ■     □     □     □     □       │  ← 7 行 (周一~周日)
│   三   □     □     ■     ■     □     □       │     每格 ~36×13px
│   四   ■     □     □     □     ■     □       │
│   五   □     ■     □     □     □     ■       │
│   六   □     □     ■     □     □     □       │
│   日   □     □     □     ■     □     □       │
│                                              │
│  □ □ □ □ ■   低 → 高   日均 ¥X.XX           │  ← 图例, 11px
└──────────────────────────────────────────────┘
```

### 像素预算 (296×152)

| 区域 | 高度 | 说明 |
|------|------|------|
| 顶部留白 | 4px | padding-top |
| 标题行 | 16px | "近30日消费" + 日期范围 |
| 间距 | 2px | |
| 周标签行 | 10px | 每列顶部标注起始日期 |
| 间距 | 2px | |
| 热力图主体 | 97px | 7×13px 格子 + 6×1px 间隙 |
| 间距 | 4px | |
| 图例行 | 11px | 色块 + 日均金额 |
| 底部留白 | 6px | padding-bottom |
| **合计** | **152px** | |

| 区域 | 宽度 |
|------|------|
| 左侧留白 | 6px |
| 星期标签 | 18px ("一"~"日") |
| 间距 | 2px |
| 6列格子 | 6×36px + 5×2px = 226px |
| 右侧留白 | 44px |
| **合计** | **296px** |

## 色彩层级

### ⚠️ 灰度验证结果（2024-06-22 实测）

推送到设备测试了 5 级 div `backgroundColor` 灰阶（#fff, #ccc, #888, #444, #000）：

- **#ffffff, #cccccc, #888888 → 全部显示为白色**
- **#444444, #000000 → 全部显示为黑色**

**结论：Canvas API 服务端对 div 元素不做抖动处理，仅做 50% 阈值二值化。** 必须使用 `img` 元素 + `img-dither-*` + `img-levels-*` 类来实现灰阶。

### 实现方案：纯 Python 生成 PNG + Canvas img 元素

用 Python 标准库（`struct` + `zlib`）生成灰度 PNG 图片，以 base64 data URI 嵌入 `img` 元素，配合抖动类实现可控灰阶：

```
img 元素 tw 类: "img-dither-diffusion img-levels-8"
```

灰度值映射（PNG 像素值 0-255）：

| 等级 | 消费占比 | PNG 灰度值 | 含义 |
|------|----------|-----------|------|
| 0 | cost = 0 或无数据 | 255 (全白) | 无消费 |
| 1 | 0 < ratio ≤ 25% | 210 | 低 |
| 2 | 25% < ratio ≤ 50% | 160 | 中 |
| 3 | 50% < ratio ≤ 75% | 100 | 高 |
| 4 | 75% < ratio ≤ 100% | 40 | 峰值 |

**当日标记**：今天的格子在 PNG 中绘制 2px 黑色边框（其他格子 1px 浅灰边框）。

层级阈值基于近 30 天内的最大消费值动态计算。

### 布局策略：混合方案

- **标题、日期标签、图例文字**：用 `div`/`span` 文本元素（黑白文字够用）
- **热力图格子区域**：生成一张完整 PNG（226×97px），作为单个 `img` 元素
- **图例色块**：5 个小 PNG 各自作为 `img` 元素

## 数据来源

### 主数据源：`imported_daily_costs`（usage_history.json）

DeepSeek 平台导出的 ZIP 文件（含 `cost-YYYY-M.csv`），通过 `--import-usage` 导入。CSV 中每日 `cost` 字段汇总即为当日消费。

### 兜底数据源：余额快照差值（balance_history.json）

对于 CSV 未覆盖的日期（通常是导入后新产生的消费），通过相邻两天的余额快照计算：
```
daily_consumption = yesterday_balance - today_balance
```

### 数据收集流程

```
近30天日期范围 [today-29, today]
    │
    ├── 日期在 imported_daily_costs 中？
    │   ├── 是 → 使用导入的 cost
    │   └── 否 → 有相邻两天的余额快照？
    │       ├── 是 → 使用余额差值
    │       └── 否 → 无数据 (level 0)
    │
    └── 汇总为 {date_str: Decimal} 字典
```

## 实现清单

### 需新增文件

| 文件 | 说明 |
|------|------|
| `deepseek_balance/heatmap.py` | 数据收集 + Canvas payload 构建 |

### 需修改文件

| 文件 | 改动 |
|------|------|
| `deepseek_balance/main.py` | 添加 `--heatmap` 参数和处理函数 |

### 无需改动

| 文件 | 原因 |
|------|------|
| `layout.py` | 热力图为独立视图，不复用余额布局 |
| `usage_data.py` | 直接使用现有 `get_daily_cost()` / `load_usage()` |
| `history.py` | 直接使用现有 `load_history()` |
| `dot_push.py` | 复用 `push_canvas()`，无需修改 |
| `config.py` | CURRENCY 等配置复用 |

### 可复用的现有函数

- `layout.py`: `_format_balance()`, `_cny()`, `_usd()` — 金额格式化
- `layout.py`: `_element()` — Canvas 元素构建辅助（复制到 heatmap.py 避免跨模块耦合）
- `usage_data.py`: `get_daily_cost()`, `load_usage()`
- `history.py`: `load_history()` — 读取余额快照用于差值计算
- `dot_push.py`: `push_canvas()`
- `main.py`: `_handle_push()` — 复用 dry-run / 推送逻辑

## CLI 使用方式

```bash
# 推送到设备
python -m deepseek_balance.main --heatmap

# 预览 JSON 不推送
python -m deepseek_balance.main --heatmap --dry-run

# 定时刷新（与余额仪表盘分开调度）
# crontab 示例：每天 4 次
0 0 * * * /path/to/run_balance_check.sh           # 余额仪表盘
0 8 * * * /path/to/run_balance_check.sh --heatmap # 热力图（可在不同时间）
```

## 边界情况

| 情况 | 处理 |
|------|------|
| 新安装，不足 30 天数据 | 缺失日期显示为 level 0（空白格子） |
| 所有 30 天消费为 0 | 全部 level 0，不崩溃 |
| 中间某天缺失数据 | 该格 level 0，不影响其他格子 |
| 数据正好跨越两个月 | 周标签显示月份分界（如 "5/24" "6/1"） |
| e-ink 灰度表现不足 | 可降级为 3 级（0/1/3/4 → 0/1/2/3） |
| 无 usage_history.json 文件 | 全部使用余额快照差值，如也无快照则全空白 |

## Canvas API 适配说明

### 混合布局策略

经实测验证，div 的 `backgroundColor` 在服务端被阈值二值化（>50% 灰=黑，<50% 灰=白），不可用于灰阶。采用混合方案：

- **文本元素**（标题、标签、图例文字）：用 `div`/`span` + 黑白文字
- **热力图格子区**：Python 标准库生成一张完整 226×97 PNG，嵌入单个 `img` 元素
- **图例色块**：5 个 10×10 PNG 小方块，各自作为 `img` 元素
- **所有 img 元素**加入 `tw: "img-dither-diffusion img-levels-8"` 实现灰阶抖动

### PNG 生成（纯 Python，零依赖）

使用 `struct` + `zlib` 标准库构建最小灰度 PNG：
- 8-bit 灰度模式（color type 0）
- 逐行写入像素值 + filter byte
- deflate 压缩后封装 IDAT chunk
- 输出 base64 data URI 嵌入 JSON payload

格子尺寸：36×13px，间距 2px(H) / 1px(V)，1px 边框

## 后续扩展（可选）

- **多月份切换**：支持查看上个月的热力图
- **与余额视图轮播**：利用 Quote/0 的 Loop 模式自动切换两个视图
- **点击交互**：如果 Canvas API 支持，点击某天可显示详细金额
- **总消费统计**：在图例旁显示 30 天合计
