from __future__ import annotations

from copy import deepcopy


def metric(label, value, change="", status="fresh", source="官方/授权数据", as_of="最近批次"):
    return {
        "label": label,
        "value": value,
        "change": change,
        "status": status,
        "source": source,
        "as_of": as_of,
    }


COMMON = {
    "source_notes": [
        "页面只发布通过许可与质量检查的官方或授权数据；缺数时显示空缺。",
        "每个组件分别显示 value_date、fetched_at、quality_status 与 fallback，不以页面级时间覆盖差异。",
    ],
    "chart_data": [],
}


PAGE_CONFIGS = {
    "assets-equities": {
        "title": "美股",
        "eyebrow": "Equity Breadth",
        "description": "指数表现只是表层，广度、集中度、信用确认与期权结构共同决定上涨质量。",
        "metrics": [
            metric("标普 500", "5,482.31", "+0.42%", source="授权日线适配器"),
            metric("纳斯达克 100", "19,817.24", "+0.31%", source="授权日线适配器"),
            metric("200 日均线上方", "58.4%", "-0.6pp", source="成分股聚合"),
            metric("SPX−RUT 20D", "+3.2pp", "集中度升高", "stale", "成分股聚合"),
        ],
        "analysis": "指数仍处于上行结构，但中小盘确认不足。只有当广度与高收益信用同步改善，才把反弹升级为趋势。",
    },
    "assets-etfs": {
        "title": "ETF 看板",
        "eyebrow": "Cross-Asset ETFs",
        "description": "使用可交易 ETF 观察权益、久期、信用、商品和美元之间的资金迁移。",
        "metrics": [
            metric("SPY", "$548.21", "+0.42%"),
            metric("QQQ", "$486.70", "+0.31%"),
            metric("TLT", "$92.43", "-0.18%"),
            metric("HYG", "$78.94", "+0.06%"),
        ],
        "analysis": "权益 ETF 领先，但久期资产未确认。观察 HYG/LQD 是否继续相对走强。",
    },
    "assets-bonds": {
        "title": "债券",
        "eyebrow": "Duration & Credit",
        "description": "同时追踪国债久期、投资级与高收益信用，而不是只看单一收益率。",
        "metrics": [
            metric("TLT", "$92.43", "-0.18%"),
            metric("IEF", "$95.18", "-0.07%"),
            metric("LQD", "$108.34", "+0.02%"),
            metric("HYG", "$78.94", "+0.06%"),
        ],
        "analysis": "信用债相对稳定但长久期承压，当前更接近增长尚可、期限溢价偏高的组合。",
    },
    "assets-commodities": {
        "title": "商品",
        "eyebrow": "Commodity Complex",
        "description": "能源、贵金属和工业金属用来验证增长、通胀与地缘风险。",
        "metrics": [
            metric("WTI", "$78.42", "+1.20%"),
            metric("黄金", "$2,391", "-0.24%"),
            metric("铜", "$4.56", "+0.61%"),
            metric("天然气", "$2.71", "-1.40%"),
        ],
        "analysis": "油价反弹而黄金回落，短线更像增长/供给交易，尚未形成全面通胀冲击。",
    },
    "assets-fx": {
        "title": "外汇",
        "eyebrow": "Global Dollar",
        "description": "美元指数、主要货币和离岸融资压力共同定义全球美元环境。",
        "metrics": [
            metric("DXY", "104.31", "+0.12%"),
            metric("EUR/USD", "1.0824", "-0.08%"),
            metric("USD/JPY", "157.12", "+0.34%"),
            metric("USD/CNH", "7.284", "+0.10%"),
        ],
        "analysis": "美元温和偏强，日元仍是潜在波动源。若离岸基差同步走弱，风险资产压力会被放大。",
    },
    "assets-crypto": {
        "title": "加密货币",
        "eyebrow": "Crypto Market",
        "description": "现货价格、波动率、ETF 资金与杠杆结构分层展示。",
        "metrics": [
            metric("BTC", "$67,420", "+1.14%", source="OKX / Deribit"),
            metric("ETH", "$3,480", "+0.82%", source="OKX"),
            metric("BTC 30D RV", "43.2%", "+1.1pp", source="日线计算"),
            metric("BTC/ETH", "19.37", "+0.4%", source="现货比值"),
        ],
        "analysis": "现货回升但杠杆未明显扩张，结构比高费率推动的上涨更健康。",
    },
    "rates": {
        "title": "利率",
        "eyebrow": "Rates Command Center",
        "description": "从政策利率、整条收益率曲线、实际利率与拍卖需求判断金融条件。",
        "metrics": [
            metric("有效联邦基金", "5.33%", "持平", source="NY Fed / FRED"),
            metric("2Y", "4.72%", "+2bp", source="Treasury / FRED"),
            metric("10Y", "4.31%", "+3bp", source="Treasury / FRED"),
            metric("2s10s", "-41bp", "+1bp", source="曲线计算"),
        ],
        "analysis": "曲线仍倒挂，长端小幅上行反映期限溢价而非增长加速。",
    },
    "fed-funds": {
        "title": "联邦基金利率",
        "eyebrow": "Policy Corridor",
        "description": "EFFR、SOFR、IORB 与目标区间共同刻画政策走廊。",
        "metrics": [
            metric("EFFR", "5.33%", "持平", source="NY Fed"),
            metric("SOFR", "5.32%", "-1bp", source="NY Fed"),
            metric("IORB", "5.40%", "持平", source="Federal Reserve"),
            metric("SOFR−IORB", "-8bp", "充裕", source="派生计算"),
        ],
        "analysis": "资金价格仍位于政策走廊内，暂未出现银行间流动性硬约束。",
    },
    "yield-curve": {
        "title": "收益率曲线",
        "eyebrow": "Treasury Curve",
        "description": "比较当前、1 周、1 月与 3 月前曲线，并拆分名义、实际和盈亏平衡通胀。",
        "metrics": [
            metric("曲线形态", "熊平", "长端+3bp"),
            metric("2s10s", "-41bp", "+1bp"),
            metric("3m10y", "-109bp", "+4bp"),
            metric("5s30s", "+18bp", "-2bp"),
        ],
        "analysis": "长端上行由实际利率驱动，金融条件边际收紧。10Y 若突破 4.45%，长久期资产风险上升。",
    },
    "auctions": {
        "title": "国债拍卖",
        "eyebrow": "Auction Monitor",
        "description": "未来 21 天发行日历与近 90 天拍卖质量。",
        "metrics": [
            metric("下次拍卖", "3Y", "2 天后", source="Treasury"),
            metric("发行额", "$58B", "计划"),
            metric("近次 Bid/Cover", "2.47x", "+0.08x"),
            metric("近次 Tail", "+0.4bp", "温和偏弱"),
        ],
        "analysis": "需求尚可但间接投标占比回落，关注中长端供给集中期对期限溢价的冲击。",
    },
    "real-rates": {
        "title": "实际利率",
        "eyebrow": "TIPS & Inflation",
        "description": "名义收益率拆分为实际利率与盈亏平衡通胀。",
        "metrics": [
            metric("5Y 实际利率", "2.08%", "+3bp"),
            metric("10Y 实际利率", "2.01%", "+2bp"),
            metric("10Y BEI", "2.30%", "+1bp"),
            metric("5Y5Y", "2.25%", "持平"),
        ],
        "analysis": "实际利率维持高位，成长股估值扩张空间受限；通胀预期仍大致锚定。",
    },
    "expectations": {
        "title": "利率预期",
        "eyebrow": "Policy Path",
        "description": "基于联邦基金期货的近似概率，不冒充 CME 官方 FedWatch。",
        "metrics": [
            metric("下次会议维持", "78%", "+4pp", source="ZQ 期货近似"),
            metric("降息 25bp", "22%", "-4pp", source="ZQ 期货近似"),
            metric("年末隐含利率", "4.86%", "+5bp"),
            metric("预期降息次数", "1.9", "-0.2"),
        ],
        "analysis": "市场削减短期降息定价，前端利率对弱数据的敏感度将上升。",
    },
    "fed-hawkish-dovish": {
        "title": "鹰鸽追踪",
        "eyebrow": "Fed Language Index",
        "description": "对官方声明和官员演讲进行可追溯的语言倾向分类。",
        "metrics": [
            metric("综合得分", "+0.4", "温和偏鹰", source="官方文本+模型分类"),
            metric("近 20 条鹰派", "7", "+2"),
            metric("近 20 条鸽派", "4", "-1"),
            metric("中性", "9", "持平"),
        ],
        "analysis": "政策沟通仍强调通胀风险，但劳动力市场降温使委员会内部差异扩大。",
    },
    "liquidity": {
        "title": "流动性",
        "eyebrow": "Dollar Liquidity",
        "description": "以资产负债表、Repo、离岸美元、中介能力和资产反应构成传导体系。",
        "metrics": [
            metric("LPI", "5.6 / 10", "偏紧"),
            metric("净流动性", "$5.42T", "20D -$64B", source="WALCL−RRP−TGA"),
            metric("准备金", "$3.31T", "4W -1.2%", source="Federal Reserve"),
            metric("SOFR−IORB", "-8bp", "正常", source="NY Fed"),
        ],
        "analysis": "缓冲仍在但边际收缩，若 TGA 上升同时准备金下降，风险资产对冲需求会加速。",
    },
    "transmission-chain": {
        "title": "美元流动性传导链",
        "eyebrow": "Six-Layer Pressure Index",
        "description": "能源、离岸美元、在岸 Repo、银行负债表、中介能力和资产反应六层评分。",
        "metrics": [
            metric("总压力", "5.6 / 10", "+0.3"),
            metric("能源", "4 / 10", "稳定"),
            metric("离岸美元", "6 / 10", "偏紧"),
            metric("Repo", "5 / 10", "缓冲下降"),
            metric("银行负债表", "6 / 10", "收缩"),
            metric("中介能力", "4 / 10", "正常"),
        ],
        "analysis": "当前薄弱点是离岸美元与银行负债表的共振，尚未扩散为全面中介压力。",
    },
    "fed-balance-sheet": {
        "title": "美联储资产负债表",
        "eyebrow": "H.4.1",
        "description": "总资产、国债、MBS、准备金和净流动性统一到可比较单位。",
        "metrics": [
            metric("总资产", "$7.22T", "周 -$8B", source="Fed H.4.1"),
            metric("国债持有", "$4.52T", "周 -$4B"),
            metric("MBS", "$2.31T", "周 -$5B"),
            metric("净流动性", "$5.42T", "20D -$64B"),
        ],
        "analysis": "缩表速度温和，但财政账户变化使市场可用流动性波动更大。",
    },
    "operations": {
        "title": "公开市场操作",
        "eyebrow": "Open Market Operations",
        "description": "RMP、SOMA、SRF 和最近操作记录。",
        "metrics": [
            metric("当日 RMP", "$0.0B", "无操作", source="NY Fed"),
            metric("30D 累计", "$18.4B", "+$2.1B"),
            metric("SRF", "$0.0B", "未使用"),
            metric("SOMA", "$6.74T", "周 -$9B"),
        ],
        "analysis": "常备工具未激活，Repo 压力仍属于价格波动而非硬约束。",
    },
    "rrp-tga": {
        "title": "RRP 与 TGA",
        "eyebrow": "Fiscal Liquidity",
        "description": "财政收支、发行和逆回购缓冲共同决定未来 14 天净抽水。",
        "metrics": [
            metric("RRP", "$0.32T", "日 -$9B", source="NY Fed"),
            metric("TGA", "$0.76T", "日 +$24B", source="Treasury DTS"),
            metric("7D 净冲击", "-$84B", "抽水"),
            metric("14D 净冲击", "-$126B", "偏紧"),
        ],
        "analysis": "发行与税收推高 TGA，RRP 缓冲继续下降，短期流动性偏紧。",
    },
    "reserves": {
        "title": "银行准备金",
        "eyebrow": "Reserve Adequacy",
        "description": "准备金水平、变化速度与银行体系规模共同判断充裕度。",
        "metrics": [
            metric("准备金", "$3.31T", "4W -1.2%"),
            metric("占银行资产", "13.8%", "-0.2pp"),
            metric("8W Z-score", "-0.84", "偏低"),
            metric("状态", "充裕", "缓冲下降"),
        ],
        "analysis": "绝对水平尚未进入稀缺区，但下降速度值得跟踪。",
    },
    "global-dollar": {
        "title": "全球美元",
        "eyebrow": "Offshore Funding",
        "description": "跨币种基差、美元指数与央行互换衡量离岸融资压力。",
        "metrics": [
            metric("USD/JPY 3M basis", "-34bp", "-6bp", source="授权 basis 适配器"),
            metric("USD/CNH 3M basis", "-91bp", "-12bp", source="授权 basis 适配器"),
            metric("EUR/USD 3M basis", "+4bp", "+1bp"),
            metric("央行互换", "$0.12B", "+$0.02B"),
        ],
        "analysis": "亚洲美元融资偏紧，若 USD/CNH 基差继续走弱，应降低高杠杆风险敞口。",
    },
    "subsurface": {
        "title": "次表层资金流",
        "eyebrow": "Repo Microstructure",
        "description": "SOFR 尾部分位、成交量、SRF 与央行互换捕捉均衡价格下的摩擦。",
        "metrics": [
            metric("综合压力", "4.2 / 10", "正常"),
            metric("SOFR 99P−IORB", "+4bp", "尾部温和"),
            metric("成交量 Z", "-0.42", "正常"),
            metric("SRF 激活", "否", "0 天/30D"),
        ],
        "analysis": "次表层尚无硬压力，主要风险来自尾部融资成本缓慢抬升。",
    },
    "economy": {
        "title": "经济数据",
        "eyebrow": "US Macro Pulse",
        "description": "增长、就业、通胀与消费四个模块分别保留官方发布日期与修订版本。",
        "metrics": [
            metric("实际 GDP", "+2.1%", "年化", source="BEA / FRED"),
            metric("失业率", "4.1%", "+0.1pp", source="BLS"),
            metric("核心 CPI", "+3.3%", "同比 -0.1pp", source="BLS"),
            metric("实际消费", "+0.3%", "环比", source="BEA"),
        ],
        "analysis": "增长温和放缓、通胀回落但不均衡，软着陆仍是基准情景。",
    },
    "gdp": {
        "title": "GDP",
        "eyebrow": "Growth Decomposition",
        "description": "实际 GDP、消费、投资、政府和净出口贡献。",
        "metrics": [
            metric("实际 GDP", "+2.1%", "环比年化", source="BEA / GDPC1"),
            metric("消费贡献", "+1.4pp", "主引擎"),
            metric("投资贡献", "+0.4pp", "改善"),
            metric("净出口", "-0.2pp", "拖累"),
        ],
        "analysis": "消费仍支撑增长，但投资和库存的波动增加下一季度不确定性。",
    },
    "employment": {
        "title": "就业",
        "eyebrow": "Labor Market",
        "description": "非农、失业率、时薪、职位空缺与初请共同判断供需平衡。",
        "metrics": [
            metric("非农新增", "+176K", "低于 3M 均值", source="BLS"),
            metric("失业率", "4.1%", "+0.1pp"),
            metric("时薪", "+3.9%", "同比 -0.2pp"),
            metric("职位空缺", "8.14M", "-0.22M"),
        ],
        "analysis": "劳动力需求正常化但未断裂，工资降温给通胀继续回落提供空间。",
    },
    "inflation": {
        "title": "通胀",
        "eyebrow": "Inflation Stack",
        "description": "CPI、PCE、PPI、住房与市场通胀预期分层展示。",
        "metrics": [
            metric("CPI", "+3.0%", "同比 -0.2pp", source="BLS"),
            metric("核心 CPI", "+3.3%", "同比 -0.1pp"),
            metric("核心 PCE", "+2.8%", "持平", source="BEA"),
            metric("10Y BEI", "2.30%", "+1bp", source="FRED"),
        ],
        "analysis": "商品通胀受控，住房与服务仍粘性。通胀回落路径存在，但速度不足以支持快速宽松。",
    },
    "consumer": {
        "title": "消费",
        "eyebrow": "Household Demand",
        "description": "零售、实际消费、储蓄率、信贷与消费者信心。",
        "metrics": [
            metric("零售销售", "+0.4%", "环比", source="Census"),
            metric("实际 PCE", "+0.3%", "环比", source="BEA"),
            metric("储蓄率", "3.9%", "-0.2pp"),
            metric("消费者信心", "68.2", "+2.1"),
        ],
        "analysis": "消费仍有韧性但缓冲下降，低收入家庭的信用压力是领先风险。",
    },
    "volatility": {
        "title": "波动率",
        "eyebrow": "Volatility Regime",
        "description": "权益、利率、外汇、商品与信用波动率的跨资产状态。",
        "metrics": [
            metric("VIX", "15.8", "-0.7pt", source="Cboe / FRED fallback"),
            metric("MOVE", "96", "+2"),
            metric("VIX9D", "14.9", "contango"),
            metric("VXTLT", "17.4", "+0.8"),
        ],
        "analysis": "权益波动率偏低而利率波动率仍高，风险被压在资产负债表与期限溢价层。",
    },
    "volatility-dashboard": {
        "title": "波动率全景",
        "eyebrow": "30-Index Vol Map",
        "description": "按风险来源聚合 30 个波动率指数，并生成 Vol Trade Map。",
        "metrics": [
            metric("升温指标", "11 / 30", "+3"),
            metric("降温指标", "14 / 30", "-2"),
            metric("权益风险", "低", "VIX 15.8"),
            metric("利率风险", "中高", "MOVE 96"),
        ],
        "analysis": "最需要对冲的是利率波动而非现货股指；跨资产分化仍显著。",
    },
    "vix": {
        "title": "VIX",
        "eyebrow": "Equity Volatility",
        "description": "现货水平、期限结构、分位数与实现波动率对照。",
        "metrics": [
            metric("VIX", "15.8", "-0.7pt"),
            metric("1Y 分位", "34%", "正常偏低"),
            metric("1M−Spot", "+1.6pt", "contango"),
            metric("SPX 20D RV", "12.4%", "IV 溢价 3.4pt"),
        ],
        "analysis": "期限结构健康但保护价格偏低，事件前短端波动率存在补涨空间。",
    },
    "credit": {
        "title": "美国信用市场",
        "eyebrow": "Credit Cycle",
        "description": "IG/HY 利差、融资成本、贷款标准和跨资产确认。",
        "metrics": [
            metric("IG OAS", "89bp", "+2bp", source="ICE BofA / FRED"),
            metric("HY OAS", "322bp", "+5bp", source="ICE BofA / FRED"),
            metric("HY−IG", "233bp", "+3bp"),
            metric("NFCI", "-0.42", "宽松", source="Chicago Fed / FRED"),
        ],
        "analysis": "绝对利差仍不高，但 HY 扩张速度快于 IG，是风险偏好边际走弱的早期信号。",
    },
    "credit-spreads": {
        "title": "信用利差",
        "eyebrow": "Spread Stack",
        "description": "按 IG、BBB、BB、B、CCC 拆分 OAS 与 all-in yield。",
        "metrics": [
            metric("IG OAS", "89bp", "+2bp"),
            metric("BBB OAS", "118bp", "+3bp"),
            metric("BB OAS", "205bp", "+4bp"),
            metric("CCC OAS", "825bp", "+18bp"),
        ],
        "analysis": "尾部评级先行走弱，但尚未扩散到投资级。",
    },
    "credit-cds": {
        "title": "CDS 代理监控",
        "eyebrow": "Proxy — Not Markit",
        "description": "未取得商业 CDX/CDS 授权前，只展示透明的可交易代理，不冒充真实报价。",
        "metrics": [
            metric("银行代理", "+1.8%", "KBWB 14D−SPX 14D", "estimated", "Yahoo 代理"),
            metric("主权代理", "+9bp", "10Y 变化", "estimated", "Treasury 代理"),
            metric("HY 保护代理", "322bp", "+5bp", "fallback", "ICE BofA OAS"),
            metric("真实 CDX", "未授权", "不展示", "error", "需商业许可"),
        ],
        "analysis": "当前只可判断信用方向，不能用于精确对冲或交易报价。",
    },
    "credit-stress": {
        "title": "信用压力仪表盘",
        "eyebrow": "Five-Factor Stress",
        "description": "利差水位、变化速度、贷款标准、市场流动性与跨资产背离五分量。",
        "metrics": [
            metric("综合压力", "38 / 100", "+4"),
            metric("利差水位", "24 / 100", "低"),
            metric("变化速度", "46 / 100", "升温"),
            metric("贷款标准", "52 / 100", "偏紧"),
            metric("市场流动性", "31 / 100", "正常"),
        ],
        "analysis": "压力仍低于警戒线，但变化速度与贷款标准方向不利。",
    },
    "trade-map": {
        "title": "今日 Trade Map",
        "eyebrow": "Cross-Asset Decision Map",
        "description": "将已审核的宏观主线映射到受益资产、回避资产、触发器、证伪条件与风险预算。",
        "metrics": [],
        "chart_data": [],
        "analysis": "当前尚无通过证据完整性检查的 Trade Map 批次，页面不展示估算或演示结论。",
        "sections": [
            {
                "title": "数据缺口",
                "body": "需要已发布 Thesis、可追溯 EvidenceItem、Trigger、Invalidation、Outcome 以及同批次跨资产快照。",
            },
            {
                "title": "目标字段",
                "body": "as_of、regime、confidence、beneficiary_assets、avoid_assets、risk_budget、triggers、invalidations、confirmation_matrix、divergences、source_ids、batch_id、review_status。",
            },
        ],
        "source_notes": ["仅在当日必需数据完整且研判通过审核后发布。"],
    },
    "volatility-move": {
        "title": "MOVE 指数",
        "eyebrow": "Treasury Volatility",
        "description": "跟踪美债期权隐含波动率、曲线波动分解与历史分位。",
        "metrics": [],
        "chart_data": [],
        "analysis": "MOVE 是授权指数；在取得可公开展示的许可之前，不生成或填充代理数值。",
        "sections": [
            {
                "title": "数据缺口",
                "body": "需要 ICE MOVE 延迟或收盘数据的展示与再分发许可，以及可选的期限分量。",
            },
            {
                "title": "目标字段",
                "body": "value_date、move_close、move_change_1d、move_change_5d、percentile_1y、percentile_10y、term_components、source_id、fetched_at、license_scope、quality_status。",
            },
        ],
        "source_notes": ["建议向 ICE Data Indices 采购 MOVE 延迟、收盘或历史数据权限。"],
    },
    "fx-vol": {
        "title": "外汇波动率",
        "eyebrow": "FX Volatility",
        "description": "比较主要货币对的隐含波动率、实现波动率、风险逆转与期限结构。",
        "metrics": [],
        "chart_data": [],
        "analysis": "尚未接入具备公开展示授权的 FX 期权波动率面，页面保持空状态。",
        "sections": [
            {
                "title": "数据缺口",
                "body": "需要 G10 及主要新兴市场货币对的 ATM IV、25Δ risk reversal、butterfly 与日线现货历史。",
            },
            {
                "title": "目标字段",
                "body": "pair、tenor、atm_iv、realized_vol_20d、risk_reversal_25d、butterfly_25d、iv_rv_spread、percentile、value_date、source_id、license_scope、quality_status。",
            },
        ],
        "source_notes": ["优先询价 CME FX/CVOL、LSEG、Bloomberg 或其他允许网页展示的授权供应商。"],
    },
    "implied-vs-realized": {
        "title": "隐含 vs 实现波动率",
        "eyebrow": "Implied / Realized Volatility",
        "description": "按资产和时间窗口对比期权隐含波动率、实现波动率与波动率风险溢价。",
        "metrics": [],
        "chart_data": [],
        "analysis": "期权链和可追溯日线尚未形成同批次数据，因此不发布 IV-RV 差值。",
        "sections": [
            {
                "title": "数据缺口",
                "body": "需要授权期权链、标的收盘价、统一交易日历与稳定的 ATM IV 选取方法。",
            },
            {
                "title": "目标字段",
                "body": "instrument、tenor、atm_iv、realized_vol_5d、realized_vol_20d、realized_vol_60d、variance_risk_premium、percentile、value_date、batch_id、source_id、quality_status。",
            },
        ],
        "source_notes": ["期权与现货数据必须同批次对齐；缺任一输入时不生成结果。"],
    },
    "supply-chain": {
        "title": "AI 算力供应链",
        "eyebrow": "AI Compute Supply Chain",
        "description": "连接晶圆代工、先进封装、HBM、加速器与下游需求的公开证据链。",
        "metrics": [],
        "chart_data": [],
        "analysis": "五环节实际供需数据尚未完成授权与人工校验，页面不使用合成覆盖率或产能数值。",
        "sections": [
            {
                "title": "数据缺口",
                "body": "需要五环节快照、供需状态、产能事件、产品路线图、上下游依赖及每条证据的审核状态。",
            },
            {
                "title": "目标字段",
                "body": "node、period、supply_capacity、demand_capacity、coverage_ratio、lead_time、status、event_type、evidence_url、confidence、reviewed_at、source_id、license_scope。",
            },
        ],
        "source_notes": ["免费层使用公司 IR、SEC 和交易所公告；专有供需估算需单独采购授权。"],
    },
    "supply-chain-foundry": {
        "title": "晶圆代工",
        "eyebrow": "Foundry Capacity",
        "description": "跟踪先进制程产能、利用率、市占率、工厂爬坡与主要客户需求。",
        "metrics": [],
        "chart_data": [],
        "analysis": "晶圆厂月度先进制程利用率通常不公开；在没有授权估算时必须显示数据缺口。",
        "sections": [
            {
                "title": "可免费补齐",
                "body": "公司季报与法说会、月度营收、CapEx、节点路线图、新厂投产时间及公司指引。",
            },
            {
                "title": "目标字段",
                "body": "company、fab、location、process_node、wafer_capacity_monthly、utilization_rate、market_share、revenue、capex、guidance_period、status、source_id、confidence。",
            },
        ],
        "source_notes": [
            "利用率与市占率建议询价 TrendForce、TechInsights 或 Omdia，并单独确认网页展示权。"
        ],
    },
    "supply-chain-packaging": {
        "title": "先进封装",
        "eyebrow": "Advanced Packaging",
        "description": "跟踪 CoWoS、SoIC 及其他 AI 加速器封装产能、供需缺口与扩产进度。",
        "metrics": [],
        "chart_data": [],
        "analysis": "尚无经许可的封装月产能和需求拆分，不发布供需缺口百分比。",
        "sections": [
            {
                "title": "数据缺口",
                "body": "需要各封装平台月产能、在建产能、良率、需求分配、交付周期和主要 OSAT 参与者。",
            },
            {
                "title": "目标字段",
                "body": "company、platform、period、capacity_monthly、planned_capacity、yield_rate、demand_monthly、coverage_ratio、lead_time_weeks、customer_mix、source_id、confidence。",
            },
        ],
        "source_notes": [
            "免费证据优先来自公司 IR；精确产能与客户分配建议购买 SemiAnalysis、TechInsights 或 TrendForce。"
        ],
    },
    "supply-chain-hbm": {
        "title": "HBM 内存",
        "eyebrow": "High-Bandwidth Memory",
        "description": "跟踪 HBM 代际、位产出、供需覆盖、客户认证、合约价与产能爬坡。",
        "metrics": [],
        "chart_data": [],
        "analysis": "HBM 位产出、合约价和客户分配多为专有数据；未取得来源时不用新闻传言填充。",
        "sections": [
            {
                "title": "可免费补齐",
                "body": "SK Hynix、Micron、Samsung 的法说会、财报、路线图、量产/送样/认证里程碑和 CapEx 指引。",
            },
            {
                "title": "目标字段",
                "body": "vendor、generation、stack_height、period、bit_output、capacity、demand、coverage_ratio、contract_price_change、qualification_status、customer、milestone_date、source_id、confidence。",
            },
        ],
        "source_notes": [
            "位产出、供需和价格建议向 TrendForce、TechInsights、Omdia 或 SemiAnalysis 采购。"
        ],
    },
    "supply-chain-gpu": {
        "title": "AI 加速器",
        "eyebrow": "GPU and Accelerator Supply",
        "description": "跟踪 GPU、ASIC 与系统级产品路线图、出货、交付周期、库存和单位经济性。",
        "metrics": [],
        "chart_data": [],
        "analysis": "产品出货和客户分配尚无可公开展示的稳定数据源，页面不展示估算出货量。",
        "sections": [
            {
                "title": "可免费补齐",
                "body": "厂商路线图、发布日、产品规格、数据中心收入、公司指引、出口限制与已公告的云厂商部署。",
            },
            {
                "title": "目标字段",
                "body": "vendor、product、architecture、release_date、shipment_period、units_shipped、asp、lead_time_weeks、installed_base、customer、revenue、export_scope、source_id、confidence。",
            },
        ],
        "source_notes": [
            "出货、ASP、客户分配和安装基数建议购买 SemiAnalysis Accelerator Model、TechInsights 或 Omdia。"
        ],
    },
    "supply-chain-demand": {
        "title": "AI 下游需求",
        "eyebrow": "Hyperscaler and Enterprise Demand",
        "description": "跟踪云厂商与企业 AI 资本开支、算力部署、库存吸收和变现效率。",
        "metrics": [],
        "chart_data": [],
        "analysis": "下游需求拆分尚未形成可比口径，在公司披露与研究估计未分层前不发布总需求数值。",
        "sections": [
            {
                "title": "可免费补齐",
                "body": "云厂商 CapEx、管理层指引、数据中心在建项目、电力合同、AI 相关收入披露与 SEC 分部数据。",
            },
            {
                "title": "目标字段",
                "body": "company、period、total_capex、ai_capex、capex_guidance_low、capex_guidance_high、data_center_capacity_mw、accelerator_deployments、ai_revenue、backlog、source_id、estimate_flag、confidence。",
            },
        ],
        "source_notes": [
            "公司披露可免费入库；客户级 GPU 部署与需求预测可询价 SemiAnalysis、Omdia 或 TechInsights。"
        ],
    },
}


for config in PAGE_CONFIGS.values():
    for key, value in COMMON.items():
        config.setdefault(key, deepcopy(value))
    config.setdefault(
        "sections",
        [
            {
                "title": "如何解读",
                "body": "先看水位，再看变化速度，最后用跨资产信号确认。单一指标不直接生成交易指令。",
            },
            {
                "title": "验证与失效",
                "body": "所有结论必须能被下一批官方数据验证，并明确显示失效条件与时间框架。",
            },
        ],
    )


def get_page_config(key: str) -> dict:
    return deepcopy(PAGE_CONFIGS[key])
