# 用 WorkBuddy + 麦当劳 MCP 做一个能算营养、算价格、还能下单的减脂私教

## 参赛入口

- **活动主页**：[麦当劳程序员创意开发大赛活动页](https://builderx.csdn.net/activity-site/m-code/pages)
- **项目参考仓库**：[mcd-developer-innovation-challenge](https://github.com/M-China/mcd-developer-innovation-challenge)
- **项目形态**：WorkBuddy Skill + 麦当劳 MCP，无自建后端

![image](https://files.mdnice.com/user/47561/abd17631-4c60-4ff8-ac83-7fc47eb7d4c8.png)

如果你也在参加活动，可以先收藏活动页，再按照本文的步骤复现 MCP 配置和 Skill 导入流程。

## 前言

很多“点什么”的应用只能告诉你某个套餐叫什么、多少钱，却回答不了几个更实际的问题：这顿饭到底有多少热量？蛋白质够不够？能不能把饮料换成无糖？优惠券怎么用最便宜？最后能不能直接下单？

McFit Coach 的定位，就是把这些问题串成一条完整链路：

> 根据用户的热量、蛋白质和钠预算，结合当前门店的实时菜单与套餐结构，生成一份可以计算价格、可以继续下单的麦当劳餐。

项目当前包含以下能力：

| 能力 | 说明 |
| --- | --- |
| 时段识别 | 根据当前时间识别早市、午市、晚市和夜市 |
| 营养解析 | 解析麦当劳 MCP 返回的营养数据，建立本地营养索引 |
| 选店与拉菜单 | 默认查询北京门店，用户也可以在对话中指定城市或门店 |
| 套餐替换 | 支持套餐拆解、去酱、饮料换无糖等同轮替换 |
| 组合求解 | 在热量、蛋白质、钠等约束下，枚举并筛选候选组合 |
| 最低价计算 | 结合门店券、账户券和随单购计算实际价格 |
| 确认下单 | 用户明确确认后创建订单，返回支付链接 |
| 麦麦体检卡 | 规划中的增强能力，用历史订单汇总近期营养情况 |

这里有一个重要边界：项目输出的营养数据和价格以官方实时接口为准，不构成医疗或营养建议；创建订单属于真实写操作，必须由用户明确确认，Skill 不会自动下单。

##  整体技术架构

项目采用“Skill 编排 + MCP 提供业务能力 + 本地脚本处理算法”的方式，没有额外部署后端。

```text
用户对话
   │
   ▼
WorkBuddy
   │
   ├── McFit Coach Skill（SKILL.md）
   │      ├── 触发条件与输出格式
   │      ├── MCP 工具调用顺序
   │      └── 安全确认规则
   │
   ├── 麦当劳 MCP Server（mcp.mcd.cn）
   │      ├── 时间、门店、菜单、套餐、优惠券
   │      ├── 营养、算价、订单
   │      └── Streamable HTTP + Bearer Token
   │
   └── 本地参考脚本
          ├── toon_parser.py：营养数据解析
          └── combo_solver.py：组合约束求解
```

项目目录如下：

```text
mdl/
├── SKILL.md
├── README.md
├── MCP_INTEGRATION.md
├── mcp-config.example.json
├── MCP接口实测.md
├── workbuddy.md
└── references/
    ├── toon_parser.py
    ├── combo_solver.py
    ├── toon_sample.txt
    └── nutrition_index.sample.json
```

##  使用 WorkBuddy 完成全程开发

这次开发没有先搭建传统 Web 项目，也没有单独写一个后端服务，而是从一个空 Skill 项目开始，让 WorkBuddy 负责推进整个开发过程。

###  从空 Skill 项目开始

第一步先让 WorkBuddy 创建 Skill 项目，并指定项目目录。这个阶段的目标不是马上写业务代码，而是先确认 Skill 的基本结构，例如主文件使用大写的 `SKILL.md`，参考脚本统一放入 `references/` 目录。
如下图所示是我的通过提示词来创建 Skill 项目的脚本。

![image](https://files.mdnice.com/user/47561/4ee0dbef-7308-4e35-bd1d-c98646bf66dd.png)

 

###   让 WorkBuddy 根据规划书拆解功能

项目最初的功能规划被拆成 F1 到 F8 八个模块：

- F1：时段识别
- F2：营养数据解析
- F3：选店与拉菜单
- F4：套餐拆解与件替换
- F5：热量、蛋白质、钠的组合求解
- F6：优惠券匹配和最低价计算
- F7：用户确认后创建订单
- F8：读取历史订单，生成麦麦体检卡

这里的关键不是让模型一次生成一大段代码，而是让它按照真实接口的调用顺序逐步落地，并把每次联调得到的约束记录下来。例如，规划书中曾经假设“薯条可以替换成玉米杯”，但实际调用 `query-meal-detail` 后发现，替换只能发生在套餐同一个 `round` 的候选项中，而板烧三件套的小食轮并不包含玉米杯。因此最终实现必须以真实接口返回为准。

![image](https://files.mdnice.com/user/47561/c425cd64-0f61-4f05-b696-795d135f879e.png)

> 这一轮之后，项目的核心文件已经形成：`SKILL.md` 负责触发与编排，`toon_parser.py` 处理营养数据，`combo_solver.py` 负责本地组合求解，接口实测结果则沉淀到 `MCP接口实测.md` 中。

### 用真实数据修正方案

开发中最有价值的部分不是“生成了多少代码”，而是把接口返回中的边界条件验证清楚。当前已经确认的关键事实包括：

1. `list-nutrition-foods` 返回的是 TOON 文本，不是 JSON，需要单独解析。
2. `query-meals` 的菜单价格是“元”且通常以字符串返回。
3. `calculate-price` 的价格字段是“分”，展示时必须除以 100。
4. 到店自取 `beType=1` 时，后续调用不需要传 `beCode`。
5. 套餐替换只能发生在同一轮可选项中。
6. “去酱”通过 `modification` 传递，“可乐换无糖”是同轮零加价替换。
7. `create-order` 会产生真实订单，只能在用户明确确认后调用。

## 配置自定义模型：`doubao-seed-2-1-pro-260915`

为了让 WorkBuddy 更稳定地完成长链路分析、代码生成和接口调试，需要先配置一个可用的自定义模型。本文使用的模型名称是：

```text
doubao-seed-2-1-pro-260915
```

###   添加自定义模型

在 WorkBuddy 的模型配置页面中，新增自定义模型，并填写模型标识、服务商提供的接口信息以及鉴权配置。模型名称要与平台实际支持的模型 ID 完全一致，避免出现模型列表能看到但请求时找不到模型的问题。

![配置自定义模型 doubao-seed-2-1-pro-260915](https://files.mdnice.com/user/47561/f9d49b05-3361-4c70-bc81-63c5f388b4e6.png)
 
###  测试模型连通性

保存配置后，不要直接进入复杂开发流程，先使用平台的连通性测试。只有模型能够正常返回结果，后续的 MCP 配置、Skill 调试和代码生成才有意义。

![测试 doubao-seed-2-1-pro-260915 连通性](https://files.mdnice.com/user/47561/f9dc0429-42c5-4c95-958d-0e82288be4a7.png)

测试通过后，可以让 WorkBuddy 先执行一个简单任务，例如读取 `README.md` 并总结项目结构；确认输出正常，再开始编写 Skill。这样可以把“模型不可用”和“项目代码有问题”两个故障来源分开。

##  配置麦当劳 MCP 服务

本项目使用麦当劳中国提供的远程 MCP Server，不需要自己部署服务端。参考仓库为 [M-China/mcd-mcp-server](https://github.com/M-China/mcd-mcp-server)，服务使用 Streamable HTTP 协议。

###  获取 MCP Token

1. 打开 [麦当劳 MCP 开放平台](https://open.mcd.cn/mcp)。
2. 使用手机号登录。

![image](https://files.mdnice.com/user/47561/e119d910-5b47-4cb7-b2d0-dd4af9feb541.png)

3. 进入控制台并激活 MCP 服务。
4. 创建或复制 MCP Token。 
 
 
![image](https://files.mdnice.com/user/47561/f6bd8136-5e72-4397-85ed-138484024e65.png)

###  在 WorkBuddy 中添加 MCP 配置

获取了 Token 之后复制下面的代码通过连接器来配置 MCP, 如下图所示，点开管理连接器，选择自定义配置

![image](https://files.mdnice.com/user/47561/5c9f1044-8bd7-4d81-af51-b6c83d844b04.png)

如下图所示在自定义配置值添加 MCP,

![image](https://files.mdnice.com/user/47561/469f9fd1-9381-498a-8d91-55d5d3483966.png)

> 注意替换自己的 TOKEN 

```json
{
  "mcpServers": {
    "mcd-mcp": {
      "type": "streamablehttp",
      "url": "https://mcp.mcd.cn",
      "headers": {
        "Authorization": "Bearer YOUR_MCP_TOKEN"
      }
    }
  }
}
```

mcp 配置完成后记得点击启用即可，如下图所示


![image](https://files.mdnice.com/user/47561/8acae24d-24a9-49a4-a61e-86fbfbc6fbeb.png)

 

###  本项目实际使用的工具

| 工具 | 用途 |
| --- | --- |
| `now-time-info` | 获取当前时间并进行早午晚市分流 |
| `list-nutrition-foods` | 获取营养数据，返回 TOON 文本 |
| `query-nearby-stores` | 查询附近门店和 `storeCode` |
| `query-meals` | 获取当前门店菜单、餐品编码和价格 |
| `query-meal-detail` | 获取套餐 `rounds` 和可替换项 |
| `query-store-coupons` | 查询门店优惠券 |
| `query-my-coupons` | 查询账户优惠券 |
| `calculate-price` | 计算原价、优惠和应付金额 |
| `create-order` | 用户确认后创建真实订单 |
| `order-list` | 读取历史订单，用于体检卡增强能力 |

##  McFit Coach 的核心调用链路

用户提出需求后，Skill 按下面的顺序编排 MCP 工具和本地脚本：

```text
now-time-info
    ↓
list-nutrition-foods → 本地解析 TOON 营养数据
    ↓
query-nearby-stores → 获取门店
    ↓
query-meals → 获取当前门店菜单和价格
    ↓
query-meal-detail → 拆解套餐和可替换项
    ↓
combo_solver.py → 按热量/蛋白质/钠约束筛选组合
    ↓
query-store-coupons + query-my-coupons
    ↓
calculate-price → 计算最低到手价
    ↓
用户明确确认
    ↓
create-order → 返回 orderId 和支付链接
```

###  TOON 解析是一个容易忽略的坑

营养接口返回的不是常见 JSON，而是类似下面的 TOON 文本：

```text
[160]{productName,nutritionDescription,energyKj,energyKcal,protein,fat,carbohydrate,sodium,calcium}:
  猪柳麦满分,null,1288,308,16,16,24,781,213
  无糖可口可乐中杯,null,0,0,0,0,1,35,0
```

解析器需要先从首行提取字段，再处理每一条数据。`nutritionDescription` 可能为 `null`，也可能包含逗号，因此不能简单地对整行执行固定位置的 `split(',')`。项目中的 `references/toon_parser.py` 已覆盖这些边界情况。

###   本地求解，减少 MCP 调用次数

组合求解不应该把每一个候选组合都发送到远程接口。项目先在本地枚举“主餐 × 小食 × 饮品”，根据热量、蛋白质和钠的预算过滤出 Top-K，再对少量候选方案调用 `calculate-price`。

这样做有两个好处：

- 减少网络请求，避免触发 MCP 限流。
- 组合约束逻辑可以离线测试，调试效率更高。

##  一次真实联调：从需求到价格

以用户输入下面这句话为例：

```text
 查询天通苑附近的店铺 并给我推荐一份套餐 
```
得到的结果如下图所示

![image](https://files.mdnice.com/user/47561/11569600-89d7-4e70-aba3-39a10097c2c1.png)
 
![image](https://files.mdnice.com/user/47561/080a2ebe-b11f-4763-9a1b-945ffc5b4590.png)

等待流程跑完， 我们输入下单等待其生成订单即可，如下图所示

![image](https://files.mdnice.com/user/47561/7436e44e-557f-4d80-aa41-bbcb829a31ed.png)

![image](https://files.mdnice.com/user/47561/cbd2c960-701e-4e63-b8af-208ac5a7aed6.png)

点击链接进行打开二维码进行付款
![image](https://files.mdnice.com/user/47561/9eb04302-729c-4c9c-b343-283a7a28f301.png)

此时手机扫码效果如下图所示

![e63194dc1158063396be5b8870ee2006](https://files.mdnice.com/user/47561/e0a023aa-80f9-460d-ba5a-8c031b049e8e.jpg)

所有商品均已加入到购物车中，只需要我们支付就可以了。 
 
##  总结

McFit Coach 的核心并不是“让模型推荐一个汉堡”，而是把实时菜单、营养数据、套餐结构、组合约束、优惠券和下单确认串成一条可复现的工作流。
WorkBuddy 负责把需求拆解、Skill 编排、代码生成和联调记录连接起来；麦当劳 MCP 提供真实业务数据和操作能力；本地脚本则承担 TOON 解析和组合求解。三者组合后，一个不需要自建后端的餐饮类智能 Skill 也可以完成从需求到实测的完整闭环。

> 如果你正在参加麦当劳程序员创意开发大赛，可以从活动入口开始了解规则，再参考 [麦当劳 MCP Server 仓库](https://github.com/M-China/mcd-mcp-server) 完成服务配置，最后把自己的 Skill 导入 WorkBuddy 进行验证。

 