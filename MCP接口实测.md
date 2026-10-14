# 麦麦减脂私教 McFit Coach · MCP 接口实测记录

> 记录已连通的麦当劳 MCP（`mcp.mcd.cn`，Streamable HTTP，Bearer Token 鉴权）的真实返回，
> 作为 F1/F2 开发与解析的依据。**未列出的工具待 M1（门店参数）就位后自动补全。**
> 更新时间：2026-10-14

---

## 1. `now-time-info`（F1 时段识别 · 已验证）

**入参**：无。
**实测返回**（节选关键字段）：

```json
{
  "success": true,
  "code": 200,
  "message": "请求成功",
  "data": {
    "timestamp": 1791969979756,
    "datetime": "2026-10-14T17:26:19.756",
    "formatted": "2026-10-14 17:26:19",
    "date": "2026-10-14",
    "year": 2026, "month": 10, "day": 14,
    "dayOfWeek": "WEDNESDAY",
    "timezone": "GMT+08:00",
    "offset": "+08:00",
    "utc": "2026-10-14T09:26:19.756Z"
  }
}
```

**字段要点**：`dayOfWeek` 为英文（`MONDAY`…`SUNDAY`），`formatted` 为 `yyyy-MM-dd HH:mm:ss`。
**时段分流规则（建议）**：`formatted` 的小时 H → 早(5–10)/午(11–14)/晚(15–21)/夜市(22–4)。每次会话开头必调。

---

## 2. `list-nutrition-foods`（F2 营养解析 · 已验证 · 核心坑）

**入参**：无。
**返回结构**：`{ success, code, message, data }`，其中 `data` 是**字符串（非 JSON）**，即 TOON 文本。

### 2.1 TOON 真实格式（首行 + 样例）

```
[160]{productName,nutritionDescription,energyKj,energyKcal,protein,fat,carbohydrate,sodium,calcium}:
  猪柳麦满分,null,1288,308,16,16,24,781,213
  芝士安格斯厚牛堡,能量约鲈鱼1条,2914,696,32,44,43,897,150
  纯悦,能量约清水1杯,0,0,0,0,0,0,0
  无糖可口可乐中杯,null,0,0,0,0,1,35,0
  ...（共 160 条）
```

### 2.2 解析规则（已落地于 `references/toon_parser.py`，跑通验证）
- 首行 `[160]{字段}:` → 正则 `^\[(\d+)\]\{([^}]+)\}\s*:?$` 提取字段名。
- 数据行逗号分隔；**第一个字段=productName，末尾 7 个=数值字段**（energyKj, energyKcal, protein, fat, carbohydrate, sodium, calcium）。
- `nutritionDescription` 可能是 `null`，也可能是含中文/逗号的描述（如「能量约鲈鱼1条」）：若描述含逗号，应把末尾 7 个之外的部分合并为描述。
- 数值字段转 `int`；`null`/空 → `None`。
- **单位**：`energyKcal`=大卡（热量约束用）；`sodium`/`calcium`=毫克(mg)。

### 2.3 已验证的边界情况（真实数据）
| 项 | 原始 | 解析结果 |
|---|---|---|
| 普通 null 描述 | `猪柳麦满分,null,1288,308,...` | desc=None, kcal=308 |
| 非 null 描述含中文 | `芝士安格斯厚牛堡,能量约鲈鱼1条,2914,696,...` | desc="能量约鲈鱼1条" |
| 0 热量（无糖） | `无糖可口可乐中杯,null,0,0,0,0,1,35,0` | kcal=0, sodium=35 |
| 0 热量（清水类） | `纯悦,能量约清水1杯,0,0,0,0,0,0,0` | kcal=0 |

### 2.4 全量数据
完整 160 条为运行时实时拉取（规划书要求每次会话拉最新）。开发期样本见 `references/toon_sample.txt`（curated 40 条，覆盖各分类与边界）与 `references/nutrition_index.sample.json`（解析后的结构化索引，含自动分类）。

---

## 3. 已联调工具的真实样本（默认门店：北京 `1950139`）

> 默认点餐方式=**到店自取(beType=1)**，该方式门店**不带 beCode**，后续 `query-meals`/`query-meal-detail`/`query-store-coupons`/`calculate-price` **均不传 beCode**。这是比规划书更简化的关键点。
> 测试时间：2026-10-14。⚠️ 当时该门店 `query-store-coupons` 与 `query-my-coupons` 均返回空（无券），故 F6 仅验证了基础价逻辑。

### 3.1 `query-nearby-stores`（F3 选店 · 已验证）
- 入参：`{ beType:1, searchType:2, city:"北京", keyword:"北京" }`（`searchType=2` 按位置搜，需 city+keyword；`searchType=1` 查收藏）。
- 返回 `data[]`：`storeCode`(唯一,入参用)、`storeName`、`address`、`distance`、`reservation`(是否可预约)、`reservationTimeOptions`(预约时段)。
- **beType=1 返回项无 `beCode`**；仅 beType=5(得来速) 才有 beCode。
- 实测默认店：`1950139` 麦当劳北京西客站南候车室餐厅（营业 05:00–22:00，支持预约）。

### 3.2 `query-meals`（F3 菜单 · 已验证）
- 入参：`{ storeCode:"1950139", orderType:1, beType:1 }`（beType=1 不传 beCode）。
- 返回结构：`data.categories[]`（分类+餐品 `code`+`tags`）、`data.meals.{code}`（**详情映射表**，含 `name`/`image`/`currentPrice`/`originalPrice`/`discountType`/`canWithOrder`/`withOrder`）。
- ⚠️ **价格字段是字符串且单位为「元」**（如 `"currentPrice":"52.5"`），与 `calculate-price` 的「分」不同，两套单位要注意换算。
- 示例：`9900005462`=板烧鸡腿堡三件套 ¥52.5；`1406`=板烧鸡腿堡 ¥27；`4810`=中薯条 ¥14.5；`3071`=无糖可口可乐中杯 ¥?（见 3.4）；`1100`=巨无霸 ¥29。

### 3.3 `query-store-coupons` / `query-my-coupons`（F6 · 测试时为空）
- `query-store-coupons` 入参：`{ storeCode:"1950139", orderType:1, beType:1 }` → 实测 `data:[]`（该店当前无券）。
- `query-my-coupons` 入参：`{}` → 实测「暂无可用优惠券」。
- **结论**：F6 券匹配逻辑保留，但需等真实有券时再联调；当前 `calculate-price` 仅出基础价。

### 3.4 `query-meal-detail`（F4 拆套餐 · 已验证 · 关键约束）
- 入参：`{ storeCode:"1950139", orderType:1, beType:1, code:"9900005462" }`。
- 返回 `data.rounds[]`：每个 round 含 `id`/`name`/`choices[]`，choice 有 `code`/`name`/`isDefault`/`diffPrice`/`supportModify`/`modification`。
- ⚠️ **F4 件替换的硬约束（实测结论）**：
  1. **替换仅限同一 round 内的 `choices`**。规划书说的「薯条→玉米杯」**并非所有套餐支持**——本套餐（板烧三件套）小食轮(`id:2`)只有 `中薯条(4810)`/`大薯条(4820)`，**没有玉米杯**，因此该替换在此套餐不可行。
  2. **「去酱」真实存在且走 `modification`**：Round1 板烧鸡腿堡含 `烤味酱`(code `102201`，`selectedKey:"0-1"`)，去酱=算价/下单时传其 `unselectedKey:"0-0"`。
  3. **「可乐→无糖」是合法同轮替换**：饮料轮(`id:3`)含 `无糖可口可乐中杯`(code `3071`, `diffPrice:"+ ¥0"`)，与默认 `可乐中杯(3050)` 同轮可换，零加价。
  4. 特调项若含 `unselectedKey`，**未选中项也必须传入**（选中用 `selectedKey`、未选中用 `unselectedKey`）；`minValues=1&maxValues=1` 且单值时为必选。

### 3.5 `calculate-price`（F6 算价 · 已验证）
- 入参：`{ storeCode:"1950139", orderType:1, beType:1, items:[{productCode, quantity, (roundList?)}] }`。
- 返回价格字段**单位为「分」**（展示÷100→元）：`originalPrice`/`discount`/`price` 等；`productList[].subtotal` 也是分；`takeWayList[]`(到店取餐方式 `code`，如 `eat-in`/`take-in-store`，**F7 下单要用**)。
- 基础价实测：`9900005462` → `price:5250` = **¥52.5**（discount 0，与菜单现价一致）。
- ✅ **已验证 F4→F6 链路**：传 `roundList` 实现「去酱 + 无糖可乐」替换，构造成功返回（价格不变，因两项均 +¥0）：
  ```json
  "items":[{"productCode":"9900005462","quantity":1,
    "roundList":[
      {"round":"1","comboItemList":[{"code":"1406","quantity":1,
        "modification":{"values":[{"code":"102201","key":"0-0","quantity":1},{"code":"120512","key":"0-1","quantity":1}]}}]},
      {"round":"2","comboItemList":[{"code":"4810","quantity":1}]},
      {"round":"3","comboItemList":[{"code":"3071","quantity":1,
        "modification":{"values":[{"code":"200002","key":"0-1","quantity":1}]}}]}
    ]}]
  ```
  > 注意：`round` 字段传 round `id`（字符串 "1"/"2"/"3"）被接受；`key` 用 `selectedKey`/`unselectedKey`。

### 3.6 待补（外送场景）
| 工具 | 状态 | 说明 |
|---|---|---|
| `order-list` | ⏳ 待授权 | F8 体检卡：`comboItemList` 历史结构 |
| `delivery-query-addresses` / `delivery-query-stores` | ⏳ 外送场景 | 仅当用户选外送时联调 |

### 3.7 `create-order`（F7 · 已构造请求模板，待用户确认真实调用）
- ⚠️ **写操作，会产生真实订单**：入参（到店自取 beType=1）`storeCode`+`orderType:1`+`beType:1`（不传 beCode）+ `takeWayCode`（取自 `calculate-price.takeWayList[].code`，如 `take-in-store` 外带自提）+ `items`（沿用 §3.5 验证过的 `roundList`）+ `needTableware`。
- 已验证可用的完整请求模板（板烧三件套 去酱+无糖可乐，到店自提）：
```json
{
  "storeCode": "1950139", "orderType": 1, "beType": 1, "takeWayCode": "take-in-store", "needTableware": false,
  "items": [{"productCode":"9900005462","quantity":1,
    "roundList":[
      {"round":"1","comboItemList":[{"code":"1406","quantity":1,"modification":{"values":[{"code":"102201","key":"0-0","quantity":1},{"code":"120512","key":"0-1","quantity":1}]}}]},
      {"round":"2","comboItemList":[{"code":"4810","quantity":1}]},
      {"round":"3","comboItemList":[{"code":"3071","quantity":1,"modification":{"values":[{"code":"200002","key":"0-1","quantity":1}]}}]}
    ]}]
}
```
- 返回 `orderId` + `payH5Url`（支付链接）；支付后引导用户回复"支付完成/失败"查订单状态。
- **当前状态**：集成代码已完成；因涉及真实订单与到店/支付，执行前需用户最终回复"确认下单"再调用（或用户改提供一份示例响应完成逻辑而不实际下单）。
