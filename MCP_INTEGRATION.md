# 麦当劳 MCP 接入说明（MCP_INTEGRATION.md）

## 1. MCP Server
- **地址**：`https://mcp.mcd.cn`
- **协议**：Streamable HTTP
- **鉴权**：Bearer Token（在 `open.mcd.cn/mcp` 登录 → 控制台 → 激活获取）
- **限流**：**600 次/分钟**。组合求解在本地完成，仅对达标 Top-K 组合调 `calculate-price`，避免暴刷。

## 2. 实际使用的 Tool（真实联调结论）
| Tool | 用途 | 关键入参 | 返回要点 | 注意 |
|---|---|---|---|---|
| `now-time-info` | 时段分流 | 无 | 年月日 / 星期 / 时段 | 每次会话开头调 |
| `list-nutrition-foods` | 营养库 | 无 | **TOON 文本（非 JSON）** | 需正则解析，见 `references/toon_parser.py` |
| `query-nearby-stores` | 选店 | `beType`(1/5)、`searchType`+`city`/`keyword` | `storeCode`、`beCode` | **beType=1 无 beCode** |
| `query-meals` | 拉菜单 | `storeCode`,`orderType`,`beType` | 餐品 `code`、价格（**元/字符串**） | beType=1 不传 beCode |
| `query-meal-detail` | 拆套餐 | `code`,`storeCode`,`orderType`,`beType` | `rounds`(套餐件)、`modification` | 替换仅限同 round 内 |
| `query-store-coupons` | 门店券 | `storeCode`,`orderType`,`beType` | `couponId` | 算价前调 |
| `query-my-coupons` | 我的券 | 无 | 账户券列表 | 跨门店可用 |
| `calculate-price` | 算价 | `items`(+`couponId`/`withOrder`/`modification`/`roundList`)、`storeCode` | 原价/优惠/应付（**分**）、`takeWayList` | **返回为分，展示÷100** |
| `create-order` | 下单 | 同上 + `takeWayCode`(到店) | `orderId` + `payH5Url` | **写操作，需用户确认** |
| `order-list` | 历史订单 | 无 | 近 10 笔 `comboItemList` | F8 体检卡用 |

## 3. 调用流程（主流程编排）
```
now-time-info                   → 时段
list-nutrition-foods            → 营养索引（TOON，本地解析）
选店: query-nearby-stores / delivery-* → query-meals(storeCode)   → 候选餐品 code + 价格
query-meal-detail(code)         → rounds / modification（件替换）
本地组合求解(combo_solver.py)    → 主餐×小食×饮品 枚举，约束过滤 → Top-K
query-store-coupons + query-my-coupons → calculate-price(items)   → 最低到手价
[用户确认] create-order          → payH5Url
增强: order-list(近10笔)         → 累加热量/蛋白/钠（F8 体检卡）
```

## 4. 业务价值
- **差异化**：普通"套餐推荐"只读到菜单名；本技能解析真实营养 TOON + 套餐结构，做**热量/蛋白/钠多约束优化**，并拆解 + 替换 + 重算，最后算最低到手价、可下单——营养 + 套餐替换组合几乎无人做（蓝海）。
- **可落地**：全部能力来自官方 MCP Tool，**零自建后端**；受众广（减脂/控糖/儿童低钠是全民痛点），利于截图传播与 GitHub Star。
- **安全合规**：不存储用户数据，不下场支付，仅生成方案与支付链接；`create-order` 须用户显式授权。

## 5. 关键约束（实测结论，详见 `MCP接口实测.md`）
1. **价格单位陷阱**：`query-meals` 为「元/字符串」，`calculate-price` 返回「分」（展示÷100）。
2. **beType=1（到店自取）门店无 beCode**，后续 `query-meals`/`query-meal-detail`/`query-store-coupons`/`calculate-price` 均不传 beCode；仅 beType=5/2/6 需要。
3. **套餐件替换仅限同一 round 可选池**：规划书的"薯条→玉米杯"并非所有套餐支持（很多套餐小食轮只有薯条类）。"去酱"走 `modification` 的 `unselectedKey`；"可乐→无糖"是同轮零加价合法替换。
4. `calculate-price` 返回的 `takeWayList[].code`（如 `eat-in`/`take-in-store`）是 `create-order` 的 `takeWayCode`。
