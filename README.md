# 腾讯云服务器秒杀工具

[comment]: <> (Tencent Cloud Server Seckill Tool)

使用 Python 编写的自动化抢购脚本，支持并发抢购腾讯云轻量应用服务器。现已支持多活动配置，包括双12活动、CodingPlan活动等。

## ✨ 功能特点

- **多活动支持**：通过配置文件灵活切换不同活动（双12、CodingPlan等）
- **自动获取 Cookie**：使用 Playwright 模拟浏览器登录，自动保存登录态
- **多地域并发抢购**：支持华北、华东、华南同时抢购
- **多商品并发抢购**：可同时抢购Lite、Pro等多个套餐
- **实时库存检测**：循环检测目标商品库存状态
- **服务器时间校准**：自动获取腾讯云服务器时间，确保准时抢购
- **自动等待秒杀**：监控时间，到点自动发起抢购

## 📋 环境要求

- Python 3.8+
- Windows / macOS / Linux

## 🚀 安装步骤

### 1. 安装依赖

```bash
pip install playwright requests
playwright install chromium
```

### 2. 获取登录 Cookie

```bash
python get_cookies.py
```

运行后会自动打开浏览器，点击二维码扫码登录腾讯云。登录成功后 Cookie 会自动保存到 `cookies.json` 文件。

## ⚙️ 配置使用

### 方式一：配置文件（推荐）

编辑 `config.json` 文件：

```json
{
  "current_activity": "codingplan_lite_pro",
  "activities": {
    "double12_2025": {
      "name": "双12活动-轻量应用服务器",
      "activity_id": 162634773874417,
      "goods": [
        {
          "name": "轻量应用服务器",
          "act_id": 1784747698901873,
          "type": "bundle_budget_mc_lg4_01",
          "region_ids": [1, 4, 8],
          "goods_param_template": {
            "BlueprintId": "LINUX_UNIX",
            "area": 1,
            "ddocUnionConnect": 0,
            "goodsNum": 1,
            "imageId": "lhbp-eqora508",
            "scenario": "0",
            "timeSpanUnit": "12m",
            "zone": "",
            "type": "bundle_budget_mc_lg4_01"
          }
        }
      ],
      "seckill_time": "2026-02-12 15:00:00",
      "concurrent": true,
      "referer": "https://cloud.tencent.com/act/pro/featured-202604..."
    },
    "codingplan_lite_pro": {
      "name": "CodingPlan Lite + Pro套餐",
      "activity_id": 162319214504110,
      "goods": [
        {
          "name": "Lite套餐",
          "act_id": 1772268517129768,
          "type": "bundle_budget_mc_lg4_01",
          "region_ids": [1, 4, 8],
          "goods_param_template": {
            "BlueprintId": "LINUX_UNIX",
            "area": 1,
            "ddocUnionConnect": 0,
            "goodsNum": 1,
            "imageId": "lhbp-eqora508",
            "scenario": "0",
            "timeSpanUnit": "1m",
            "zone": "",
            "type": "bundle_budget_mc_lg4_01",
            "billmodle": "1"
          }
        },
        {
          "name": "Pro套餐",
          "act_id": 1772251690399802,
          "type": "bundle_budget_mc_lg4_01",
          "region_ids": [1, 4, 8],
          "goods_param_template": {
            "BlueprintId": "LINUX_UNIX",
            "area": 1,
            "ddocUnionConnect": 0,
            "goodsNum": 1,
            "imageId": "lhbp-eqora508",
            "scenario": "0",
            "timeSpanUnit": "1m",
            "zone": "",
            "type": "bundle_budget_mc_lg4_01",
            "billmodle": "2"
          }
        }
      ],
      "seckill_time": "2026-04-18 10:00:00",
      "concurrent": true,
      "referer": "https://cloud.tencent.com/act/pro/codingplan"
    }
  }
}
```

**参数说明**：
- `activity_id`: 活动ID（从浏览器Network面板抓取）
- `act_id`: 商品实例ID（每个套餐不同，Lite和Pro分别对应）
- `region_ids`: 抢购地域列表，1=华北，4=华东，8=华南
- `billmodle`: 计费模式，Lite=1，Pro=2
- `timeSpanUnit`: 时长单位，`1m`=1个月
- `seckill_time`: 秒杀开始时间，格式：YYYY-MM-DD HH:MM:SS
- `concurrent`: 是否并发抢购多个地域
- `referer`: 页面来源，通常固定

**配置说明**：
- `current_activity`: 当前要运行的活动标识
- `activity_id`: 活动ID，从抓包获取
- `act_id`: 商品act_id，从抓包获取（每个套餐不同）
- `region_ids`: 抢购地域列表，1=华北，4=华东，8=华南
- `seckill_time`: 秒杀开始时间，格式：YYYY-MM-DD HH:MM:SS
- `concurrent`: 是否并发抢购多个地域，true=并发，false=顺序
- `referer`: 页面来源，通常固定不动

### 方式二：直接修改代码（旧方式）

如需使用旧方式，编辑 `snap_up_server.py` 文件顶部变量。

## 🔍 如何获取活动参数（重要）

### 步骤1：打开活动页面
访问：https://cloud.tencent.com/act/pro/codingplan

### 步骤2：打开开发者工具
按 `F12` 打开，切换到 **Network** 标签

### 步骤3：筛选请求
在过滤框中输入 `check-available` 或 `do-goods`

### 步骤4：点击抢购
在页面上找到Lite或Pro套餐的【立即抢购】按钮点击

### 步骤5：复制参数
找到对应的请求，点击进入 **Payload** 标签，复制JSON内容

### 步骤6：填写config.json
根据抓包结果更新 `config.json` 中的：
- `activity_id`
- 每个商品的 `act_id`
- `goods_param_template`（根据实际返回调整）

## 🎯 运行秒杀

```bash
python snap_up_server.py
```

脚本会自动：
1. 加载登录 Cookie
2. 校准服务器时间
3. 更新 CSRF Token
4. 等待秒杀时间到点
5. 检测库存并发起抢购

## 📍 地域配置说明

| region_id | 地域 |
|-----------|------|
| 1 | 华北（北京） |
| 4 | 华东（上海） |
| 8 | 华南（广州） |

## ⚠️ 注意事项

1. **Cookie 有效期**：Cookie 有时效性，建议每次秒杀前重新获取
2. **CSRF Token**：每次登录后可能变化，秒杀前需确认更新（脚本会自动尝试读取）
3. **抢购成功率**：脚本只提升效率，不保证抢购成功
4. **仅供学习**：仅限个人学习研究使用，请勿用于商业用途
5. **参数准确性**：务必确保 `activity_id`、`act_id` 等参数正确，否则会失败

## 📊 工作原理

1. 加载 `cookies.json` 建立登录会话
2. 校准腾讯云服务器时间，确保准时
3. 到点前循环调用库存检测接口 (`check-available`)
4. 检测到有货后，并发调用下单接口 (`do-goods`)
5. 返回抢购结果

## ❓ 常见问题

**Q: 提示 "商品无购买权限"**
A: 检查是否已通过实名认证，或该商品是否对你的账号开放

**Q: 库存检测正常但抢购失败**
A: 确认 `x-csrf-token` 是否为最新值，检查 Cookie 是否有效

**Q: 抢购脚本运行正常但无响应**
A: 检查网络连接，确认秒杀时间是否正确设置

**Q: 如何更新为CodingPlan活动？**
A: 参考上方"如何获取活动参数"章节，抓包后填写 `config.json`

**Q: 想抢购多个套餐怎么办？**
A: 在 `config.json` 的 `goods` 数组中添加多个商品配置即可

## 📁 文件结构

```
CodingPlanHunter/
├── config.json           # 配置文件（活动、商品参数）
├── snap_up_server.py     # 秒杀主程序
├── get_cookies.py        # Cookie 获取脚本
├── cookies.json          # 登录 Cookie 存储（自动生成）
└── README.md             # 项目文档
```

## ⚖️ 免责声明

本项目仅供学习交流使用，请勿用于商业用途。使用本工具产生的任何后果由使用者自行承担。

---

**提示**：如需添加新活动，按照"如何获取活动参数"章节抓包后，在 `config.json` 中添加新活动配置即可。
