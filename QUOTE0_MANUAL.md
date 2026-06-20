# Quote/0 设备手册

> **来源**: [https://dot.mindreset.tech/docs/quote_0](https://dot.mindreset.tech/docs/quote_0)
> **产品页面**: [https://termo.ai/skills/quote0](https://termo.ai/skills/quote0)
> **开发者文档**: [https://dot.mindreset.tech/docs/service/open](https://dot.mindreset.tech/docs/service/open)

---

## 一、产品概述

**Quote/0** 是一款智能电子墨水屏设备，可吸附于金属表面。核心理念是：与其被动接收海量模糊信息，不如在日常生活中设置一个"有意选择"的内容入口。

> "更笨拙、更缓慢"——正因如此，它把"忽略或凝视"的权利交还给用户。

采用**云渲染技术**，能呈现丰富的排版布局和多样化信息。用户对当前内容感兴趣时，用支持 NFC 的手机轻触设备，即可调用 iOS Clip App 或 Android App 进行查看或操作。

---

## 二、技术规格

| 项目 | 规格 |
|------|------|
| 屏幕 | 2.66 英寸 电子墨水屏 |
| 分辨率 | 296 × 152 |
| 像素密度 | 125 PPI |
| 电池类型 | 锂电池 |
| 电池容量 | 800 mAh |
| 充电接口 | Type-C |
| 充电时间 | 约 1.5 小时 |
| 净重 | 52 g |
| 毛重 | 102 g |

---

## 三、连接方式

- **Wi-Fi 联网**：设备通过 Wi-Fi 连接互联网，用于接收内容更新
- **NFC 交互**：用 NFC 手机轻触设备可触发操作（iOS Clip App / Android App）
- **无蓝牙**：Quote/0 不支持蓝牙（Rand/0 设备才支持蓝牙遥控器）

### 网络相关操作

- **Reset Network**：重置网络，用于切换 Wi-Fi
- **Diagnostic Tool**：诊断工具，检查网络、服务和设备状态

---

## 四、内容模式

1. **Fixed Content（固定内容）**：持续显示同一内容
2. **Loop Content（循环内容）**：循环切换多个内容

内容通过 Content Studio 或 API 推送，支持：
- 文本内容（Text API）
- 图片内容（Image API）
- 画布内容（Canvas API）
- RSS 订阅
- 天气、日历、待办事项
- 加密货币行情

---

## 五、充电说明

- **接口**：Type-C，兼容双 Type-C  sink 模式
- **时间**：约 1.5 小时充满
- **指示灯**：充电时白色状态灯闪烁，充满后常亮
- **首次使用**：建议充满电

---

## 六、使用注意事项

- 设备预贴软磁铁不要靠近其他磁源或 MagSafe，可能导致磁性意外消除
- 电子墨水屏表面采用增强塑料涂层，**禁止使用有机溶剂或腐蚀性清洁剂**
- 部分手机壳含有磁铁或金属片会干扰 NFC，使用前建议取下手机壳
- 电池出厂约 70% 电量，建议首次使用前充满

---

## 七、开发者 API

| API | 说明 |
|-----|------|
| `GET /api/authV2/open/devices` | 获取设备列表 |
| `GET /api/authV2/open/device/:id/status` | 获取设备状态 |
| `POST /api/authV2/open/device/:id/next` | 切换到下一条内容 |
| `GET /api/authV2/open/device/:deviceId/:taskType/list` | 列出设备内容 |
| `POST /api/authV2/open/device/:deviceId/text` | 推送文本 |
| `POST /api/authV2/open/device/:deviceId/image` | 推送图片 |
| Device Settings API | 设备设置（New） |
| Canvas Content API | 画布内容控制（New） |

**限流**：10 requests/second

---

## 八、软件生态

### 官方 / 社区软件

- **Content Studio**：内容工作室
- **Quote/0 CLI**（Node.js）：命令行控制工具
- **Quote/0 Python SDK**
- **Quote/0 API Serverless Microservice**
- **DotCalendar**：天气日历
- **DotCanvas**：画布工具
- **DotClient**：客户端
- **Dot Mate**：自动化调度器
- **Dot Crypto Ticker**：加密货币行情
- **CastCard**：投屏卡片
- **Home Assistant 集成**
- **多个 MCP Server 实现**
- **iPhone Shortcuts 集成**（日历、健康提醒、晚间总结、闪念笔记等）

### 社区 3D 打印配件

- IKEA SKÅDIS 挂板支架
- 桌面充电迷你支架
- 多款桌面支架和显示器挂架
- 携带包挂钩
- Rand/0 单肩包扣

---

## 九、安全公告

共 7 篇 MSA 安全公告（2025.08 ~ 2026.04），提供负责任的披露政策。

---

## 十、相关链接

- 官网：[dot.mindreset.tech](https://dot.mindreset.tech)
- 服务状态：[dot.mindreset.tech/status](https://dot.mindreset.tech/status)
- Termo Skill 市场：[termo.ai/skills/quote0](https://termo.ai/skills/quote0)
- ClawHub：[clawhub.ai/skills/quote0](https://clawhub.ai/skills/quote0)
- GitHub：[github.com/taco-devs/termo-agent](https://github.com/taco-devs/termo-agent)
- Discord 社区：[discord.gg/Th9ne4UHRQ](https://discord.gg/Th9ne4UHRQ)
