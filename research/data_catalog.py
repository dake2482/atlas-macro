"""Auditable data-source coverage and procurement catalogue.

This file is intentionally explicit: a missing licensed feed must appear as a
product requirement, never as a plausible-looking synthetic number.
"""

from __future__ import annotations

from .models import DataRequirement

LIVE = DataRequirement.Status.LIVE
PROXY = DataRequirement.Status.PROXY
NEEDS_SOURCE = DataRequirement.Status.NEEDS_SOURCE
LICENSE_REVIEW = DataRequirement.Status.LICENSE_REVIEW
PURCHASE_REQUIRED = DataRequirement.Status.PURCHASE_REQUIRED


DATA_REQUIREMENTS = [
    {
        "key": "market-us-prices",
        "page_key": "assets-equities",
        "metric_name": "美股、ETF 与指数行情",
        "status": PURCHASE_REQUIRED,
        "vendor": "Databento / Intrinio / CTA-UTP licensed distributor",
        "product": "US Equities Mini or consolidated SIP feed with public-web display rights",
        "reason": (
            "公开网站需要外部显示/再分发权；完整行情还涉及 CTA 与 UTP "
            "Vendor Agreement。Yahoo 官方明确禁止再分发，yfinance 仅可用于开发对照。"
        ),
        "proxy_description": (
            "可使用获准公开显示的 EOD 或单交易所行情，但必须标明延迟和"
            "市场覆盖；未获权前不回退到 Yahoo 或合成价格。"
        ),
        "priority": 1,
    },
    {
        "key": "market-breadth-constituents",
        "page_key": "assets-equities",
        "metric_name": "成分股广度与 200 日均线占比",
        "status": PURCHASE_REQUIRED,
        "vendor": "S&P DJI / Nasdaq GIDS-GIW / FTSE Russell",
        "product": "Historical constituents, weights and corporate actions with derived-display rights",
        "reason": (
            "准确历史广度需要防存续者偏差的历史成分与复权行情；S&P、Nasdaq "
            "和 Russell 的成分、权重与派生展示是单独授权产品。"
        ),
        "proxy_description": (
            "改为自建的美国上市股票池广度并明确命名，不得称为 S&P 500 "
            "或 Nasdaq-100 广度。"
        ),
        "priority": 2,
    },
    {
        "key": "branded-index-data",
        "page_key": "assets-equities",
        "metric_name": "SPX、NDX、Russell 及其他品牌指数点位与历史",
        "status": PURCHASE_REQUIRED,
        "vendor": "S&P DJI / Nasdaq GIDS / FTSE Russell / Cboe Global Indices Feed",
        "product": "Index-level EOD, historical or real-time website-display licence",
        "reason": (
            "指数官网可查或有延迟图表不等于允许在 Atlas 重新发布；指数点位、"
            "历史、成分和商标使用通常需分别授权。"
        ),
        "proxy_description": "使用获许可的 SPY/QQQ/IWM 等 ETF 行情，并明确标记为代理资产。",
        "priority": 1,
    },
    {
        "key": "options-us-chain",
        "page_key": "options",
        "metric_name": "美股期权链、OI、IV 与 Greeks",
        "status": PURCHASE_REQUIRED,
        "vendor": "Cboe LiveVol-DataShop / Intrinio Enterprise / Massive Options / ORATS",
        "product": "OPRA chain plus public display, historical storage and derived-data rights",
        "reason": (
            "GEX/DEX/Vanna/Charm 需要完整期权链。当前 OPRA 数据对外展示原则上需 "
            "Vendor Agreement 或合规 Hosted Solution；业务 API 套餐不自动包含再分发权。"
        ),
        "proxy_description": (
            "可基于获许可的延迟/EOD 期权链用 BSM 重算 Greeks，所有暴露"
            "指标标记为模型估算；底层链仍必须授权。"
        ),
        "priority": 1,
    },
    {
        "key": "cftc-cot",
        "page_key": "positioning",
        "metric_name": "CFTC COT 净仓与历史百分位",
        "status": LIVE,
        "source_name": "CFTC Public Reporting Environment",
        "source_url": "https://publicreporting.cftc.gov/",
        "reason": "官方周频数据，保留周二持仓日和周五发布日。",
        "priority": 2,
    },
    {
        "key": "treasury-yield-curve",
        "page_key": "yield-curve",
        "metric_name": "美债收益率曲线与 2s10s/3m10s/5s30s",
        "status": LIVE,
        "source_name": "U.S. Treasury Daily Treasury Par Yield Curve Rates",
        "source_url": "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/",
        "priority": 1,
    },
    {
        "key": "nyfed-policy-rates",
        "page_key": "fed-funds",
        "metric_name": "SOFR、EFFR 与政策走廊",
        "status": LIVE,
        "source_name": "Federal Reserve Bank of New York Markets API",
        "source_url": "https://markets.newyorkfed.org/static/docs/markets-api.html",
        "priority": 1,
    },
    {
        "key": "fed-funds-futures",
        "page_key": "expectations",
        "metric_name": "Fed Funds 期货会议概率",
        "status": PURCHASE_REQUIRED,
        "vendor": "CME Group / CME-authorized distributor",
        "product": "FedWatch API licence or ZQ futures settlements under a CME ILA",
        "reason": (
            "不抓取或冒充 CME FedWatch；精确会议概率需授权 ZQ 期货价格，"
            "网站展示与派生概率必须纳入 CME Information License Agreement。"
        ),
        "proxy_description": (
            "可用获许可 ZQ 结算价按 CME 公开方法自行计算；无行情许可时"
            "改用纽约联储调查或自有情景，且标明非市场概率。"
        ),
        "priority": 1,
    },
    {
        "key": "treasury-real-rates",
        "page_key": "real-rates",
        "metric_name": "TIPS 实际利率与盈亏平衡通胀",
        "status": LIVE,
        "source_name": "U.S. Treasury real and nominal yield curve data",
        "source_url": "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/",
        "reason": (
            "已直连 Treasury 名义与实际收益率曲线并自行派生盈亏平衡通胀；"
            "不再经 FRED 缓存第三方序列。"
        ),
        "priority": 1,
    },
    {
        "key": "treasury-auctions",
        "page_key": "auctions",
        "metric_name": "国债拍卖日历、结果与 Bid-to-Cover",
        "status": LIVE,
        "source_name": "U.S. Treasury FiscalData auctions_query",
        "source_url": "https://fiscaldata.treasury.gov/datasets/treasury-securities-auctions-data/",
        "reason": (
            "官方日历、发行额、Bid-to-Cover、投标和分配已结构化接入；"
            "本条不包含需 when-issued 市场报价的真实 Tail。"
        ),
        "priority": 2,
    },
    {
        "key": "treasury-auction-wi-tail",
        "page_key": "auctions",
        "metric_name": "拍卖前 When-Issued 收益率与真实 Tail",
        "status": PURCHASE_REQUIRED,
        "vendor": "CME BrokerTec / LSEG-Tradeweb / Bloomberg Enterprise",
        "product": "U.S. Treasury when-issued or on-the-run market data with display rights",
        "reason": (
            "TreasuryDirect 只能提供拍卖结果；真实 Tail 需要拍卖截止前的"
            " when-issued 市场收益率。"
        ),
        "proxy_description": (
            "拍卖高收益率减前一营业日 Treasury 官方收益率，标明为 EOD 近似、"
            "不是 WI Tail。"
        ),
        "priority": 2,
    },
    {
        "key": "cme-futures-market-data",
        "page_key": "assets-commodities",
        "metric_name": "CME 股指、国债、SOFR、商品与加密期货行情",
        "status": PURCHASE_REQUIRED,
        "vendor": "CME Group / Databento / Kaiko for CME crypto",
        "product": "CME ILA, DataMine and public website distribution or derived-data rights",
        "reason": (
            "实时、延迟、EOD、历史、非显示计算、派生与公开网站展示是不同的"
            " CME 许可用途；网页可查数值不代表可再发布。"
        ),
        "proxy_description": (
            "使用 EIA、USDA、CFTC 等官方现货/库存/持仓数据，但不得冒充 CME "
            "价格、结算或期限结构。"
        ),
        "priority": 1,
    },
    {
        "key": "fed-balance-sheet",
        "page_key": "fed-balance-sheet",
        "metric_name": "美联储总资产、准备金、RRP",
        "status": LIVE,
        "source_name": "Federal Reserve H.4.1",
        "source_url": "https://www.federalreserve.gov/releases/h41/",
        "reason": "直接使用联储官方发布，避免把 FRED 聚合接口误当成通用再分发许可。",
        "priority": 1,
    },
    {
        "key": "treasury-tga",
        "page_key": "rrp-tga",
        "metric_name": "Treasury General Account",
        "status": LIVE,
        "source_name": "U.S. Treasury FiscalData Daily Treasury Statement",
        "source_url": "https://fiscaldata.treasury.gov/datasets/daily-treasury-statement/operating-cash-balance",
        "priority": 1,
    },
    {
        "key": "cross-currency-basis",
        "page_key": "global-dollar",
        "metric_name": "1M/3M/1Y 跨币种基差",
        "status": PURCHASE_REQUIRED,
        "vendor": "LSEG Data Platform-IPA / Bloomberg Enterprise Data",
        "product": "OTC cross-currency swap curves and FX forward points with public-display rights",
        "reason": (
            "可靠的离岸美元基差是 OTC 曲线数据；CME FX 期货或 DataMine 不能直接"
            "代替真实 cross-currency basis。"
        ),
        "proxy_description": (
            "Fed H.10/ECB 日度现货与 BIS 季度全球流动性只作美元压力代理；"
            "必须明确标注不是实时跨币种基差。"
        ),
        "priority": 1,
    },
    {
        "key": "bls-labor-inflation",
        "page_key": "economy",
        "metric_name": "就业、失业率、CPI 与 PPI",
        "status": LIVE,
        "source_name": "U.S. Bureau of Labor Statistics Public Data API",
        "source_url": "https://www.bls.gov/developers/",
        "priority": 1,
    },
    {
        "key": "bea-gdp-pce",
        "page_key": "gdp",
        "metric_name": "GDP 分项、PCE 与历史修订",
        "status": NEEDS_SOURCE,
        "source_name": "U.S. Bureau of Economic Analysis API",
        "source_url": "https://apps.bea.gov/api/",
        "reason": "官方 API 需免费注册密钥，待配置 BEA_API_KEY 后接入。",
        "priority": 2,
    },
    {
        "key": "census-retail",
        "page_key": "consumer",
        "metric_name": "零售销售与人口调查序列",
        "status": NEEDS_SOURCE,
        "source_name": "U.S. Census Bureau API",
        "source_url": "https://www.census.gov/data/developers.html",
        "reason": "需固化数据集、变量及修订口径。",
        "priority": 3,
    },
    {
        "key": "macro-consensus-private-surveys",
        "page_key": "economy",
        "metric_name": "宏观一致预期、经济学家调查与私营 PMI/信心指数",
        "status": PURCHASE_REQUIRED,
        "vendor": (
            "LSEG Reuters Economic Polls / Trading Economics Enterprise / "
            "S&P Global PMI / University of Michigan / The Conference Board"
        ),
        "product": "Consensus, survey and index data with website-display and archival rights",
        "reason": (
            "调查中值、历史预测、PMI、消费者信心等并非政府开放数据；"
            "终端可见或新闻引用不授予数据库存储和公开再发布权。"
        ),
        "proxy_description": (
            "免费阶段仅展示 BLS、BEA、Census 等官方实际值以及自有情景；"
            "不得将单篇新闻中的预测值拼成所谓市场一致预期。"
        ),
        "priority": 3,
    },
    {
        "key": "vix-history",
        "page_key": "vix",
        "metric_name": "VIX 现货、分位与期限结构",
        "status": PURCHASE_REQUIRED,
        "vendor": "Cboe Global Indices Feed / Cboe DataShop-CFE",
        "product": "VIX-family index and VX futures data with public website-display rights",
        "reason": (
            "Cboe 官网的历史下载只用于查询，不等于 Atlas 可再发布；VIX、VIX9D、"
            "VXTLT 等指数与 VX 期限结构需分别覆盖指数和 CFE 行情许可。"
        ),
        "proxy_description": (
            "可用已授权 SPY 价格自行计算实现波动率，并明确命名为实现波动率；"
            "不得标注成 VIX 或仿造 VX 期限结构。"
        ),
        "priority": 1,
    },
    {
        "key": "move-index",
        "page_key": "volatility-dashboard",
        "metric_name": "ICE BofA MOVE Index",
        "status": PURCHASE_REQUIRED,
        "vendor": "ICE Data Indices",
        "product": "MOVE Index licence covering history, storage and public website display",
        "reason": (
            "MOVE 是 ICE Data Indices 的品牌指数；终端权限、媒体引用或网页可见"
            "均不自动授予 Atlas 存储和公开展示历史点位的权利。"
        ),
        "proxy_description": (
            "可用 Treasury 官方收益率自行计算债券实现波动率并明确标注为自有代理，"
            "不得命名为 MOVE。"
        ),
        "priority": 1,
    },
    {
        "key": "credit-oas",
        "page_key": "credit-spreads",
        "metric_name": "IG/HY 分评级 OAS",
        "status": PURCHASE_REQUIRED,
        "vendor": "ICE Data Indices",
        "product": "ICE BofA bond-index OAS data with storage and external-display rights",
        "reason": (
            "ICE BofA OAS 序列受第三方指数许可约束；FRED API 和 FRED 页面"
            "不替代 ICE 的版权、入库或公开再分发授权。"
        ),
        "proxy_description": (
            "可展示 Treasury HQM 月度公司债曲线，以及获许可的 HYG/LQD 价格派生"
            "压力指标；必须标注为代理，不能称为 ICE BofA OAS。"
        ),
        "priority": 1,
    },
    {
        "key": "cdx-cds",
        "page_key": "credit-cds",
        "metric_name": "CDX IG/HY 与单名 CDS",
        "status": PURCHASE_REQUIRED,
        "vendor": "S&P Global CDS Pricing-Markit ICE Settlement Prices / LSEG",
        "product": "Composite CDS and CDX pricing with derived-data and public-display rights",
        "reason": (
            "CDX 与单名 CDS 的可比 composite、曲线和历史为商业估值数据；"
            "单一 SEF 成交或新闻报价不等于完整市场序列。"
        ),
        "proxy_description": (
            "可将公开 SEC SDR/SEF 的稀疏成交与获许可的 HYG、LQD、银行 ETF "
            "作为代理并披露覆盖缺口，不得冒充 Markit composite。"
        ),
        "priority": 1,
    },
    {
        "key": "crypto-spot-perps",
        "page_key": "crypto-derivatives",
        "metric_name": "BTC 现货、永续 Funding 与 OI",
        "status": LICENSE_REVIEW,
        "vendor": "OKX data licensing / Kaiko",
        "product": "Spot and derivatives feed with written public-display and redistribution rights",
        "reason": (
            "OKX 公共 API 的技术可访问性不等于允许商业公开再展示、长期缓存或"
            "跨交易所聚合；上线前需书面确认，或采购 Kaiko 等授权再分销源。"
        ),
        "proxy_description": (
            "法律审核通过前仅用于开发对照；如按交易所单独展示，仍需保留来源、"
            "延迟和条款版本，不得宣称全市场聚合。"
        ),
        "priority": 1,
    },
    {
        "key": "crypto-options",
        "page_key": "crypto-derivatives",
        "metric_name": "BTC 期权 IV、Skew、PCR 与 Max Pain",
        "status": LICENSE_REVIEW,
        "vendor": "Deribit data licensing / Kaiko",
        "product": "Options chain with written public-display, storage and derived-data rights",
        "reason": (
            "Deribit 公共 API 文档不单独构成 Atlas 的公开再分发许可；期权链、"
            "历史存储及 IV/Skew/Max Pain 等派生展示均需确认权利。"
        ),
        "proxy_description": (
            "取得底层链许可后可自行计算并标注模型假设；未获权前不发布由公开 API "
            "批量缓存得到的历史期权面。"
        ),
        "priority": 1,
    },
    {
        "key": "btc-etf-flows",
        "page_key": "crypto-derivatives",
        "metric_name": "美国现货 BTC ETF 资金流",
        "status": PURCHASE_REQUIRED,
        "vendor": "FactSet Funds / LSEG Lipper / CoinGlass Enterprise; Farside by written permission",
        "product": "Daily primary-market fund flows with public-display and archival rights",
        "reason": (
            "精确日流量是商业基金流数据；Farside 网页可读不等于可复制历史表，"
            "CoinGlass 也需 Enterprise/定制再分发授权。"
        ),
        "proxy_description": (
            "可用发行人官方 shares outstanding 与 NAV 的日变动估算申赎并标注"
            "估算口径、缺失日和价格效应，不称为精确净流入。"
        ),
        "priority": 2,
    },
    {
        "key": "coinglass-liquidations",
        "page_key": "crypto-derivatives",
        "metric_name": "全市场清算、聚合 OI 与多空比",
        "status": PURCHASE_REQUIRED,
        "vendor": "CoinGlass Enterprise / Kaiko / Coin Metrics",
        "product": "Aggregated derivatives feed with explicit external-redistribution rights",
        "reason": (
            "CoinGlass Standard/Professional 的商业使用不等于可向公众再分发；"
            "公开产品需 Enterprise 或书面定制授权，并核对交易所上游权利。"
        ),
        "proxy_description": (
            "可分别接入已通过条款审核的交易所数据并展示逐场所指标；"
            "不能据此声称覆盖全市场，也不合成不存在的清算数据。"
        ),
        "priority": 2,
    },
    {
        "key": "official-fed-documents",
        "page_key": "fed",
        "metric_name": "FOMC 声明、演讲与公告",
        "status": LIVE,
        "source_name": "Federal Reserve official RSS and documents",
        "source_url": "https://www.federalreserve.gov/feeds/feeds.htm",
        "reason": "官方 RSS 元数据、原文链接和去重已接入；鹰鸽评分仍须引用原文并经审核。",
        "priority": 2,
    },
    {
        "key": "licensed-news",
        "page_key": "news",
        "metric_name": "宏观与市场新闻流",
        "status": PURCHASE_REQUIRED,
        "vendor": "Reuters Connect / LSEG News / Dow Jones Newswires-Factiva",
        "product": "Publication or external-portal licence with display, archive and excerpt rights",
        "reason": (
            "标准桌面、终端或内部 feed 通常不允许把新闻发布到公开网站；"
            "Reuters 需 Connect/出版授权，Dow Jones 需明确公开数字产品用途。"
        ),
        "proxy_description": (
            "免费阶段仅接政府、央行、公司等官方 RSS，保存标题、时间、来源、外链"
            "和自有摘要；Google News 只作发现入口，不抓取或托管媒体正文。"
        ),
        "priority": 2,
    },
    {
        "key": "sellside-research",
        "page_key": "research",
        "metric_name": "投行研报元数据与机构观点",
        "status": PURCHASE_REQUIRED,
        "vendor": "FactSet Research Connect-Aftermarket Research / S&P Investment Research / AlphaSense",
        "product": "Contributor entitlements plus rights for the intended user and display surface",
        "reason": (
            "研报权限通常按贡献机构、公司和命名用户授予，并不允许公开网页展示；"
            "即使企业订阅可检索，也不能批量托管正文或 PDF。"
        ),
        "proxy_description": (
            "公开版只保存机构、标题、日期、资产、立场、原文链接和 Atlas 原创摘要；"
            "正文仅可在供应商授权的登录环境中按用户权限打开。"
        ),
        "priority": 2,
    },
    {
        "key": "fund-letters",
        "page_key": "fund-letters",
        "metric_name": "基金信函元数据与原创中文摘要",
        "status": NEEDS_SOURCE,
        "source_name": "Fund official websites",
        "reason": (
            "需建立基金官网白名单、许可记录和删除机制；公开可下载不等于允许 Atlas "
            "再次托管，尤其不能默认镜像 PDF。"
        ),
        "proxy_description": "仅保存元数据、官方外链和基于合法阅读的原创摘要，不托管原文或 PDF。",
        "priority": 3,
    },
    {
        "key": "sec-company-fundamentals",
        "page_key": "ai-company",
        "metric_name": "公司三年财务与申报",
        "status": NEEDS_SOURCE,
        "source_name": "SEC EDGAR submissions and company facts",
        "source_url": "https://www.sec.gov/search-filings/edgar-application-programming-interfaces",
        "reason": "适配器已就绪，待公司 CIK 映射和 SEC_USER_AGENT 配置。",
        "priority": 2,
    },
    {
        "key": "ai-company-prices",
        "page_key": "ai-company",
        "metric_name": "AI 产业公司 K 线与估值",
        "status": PURCHASE_REQUIRED,
        "vendor": "LSEG / FactSet / S&P Capital IQ / exchange-authorized distributors",
        "product": "Global equities prices with exchange-level public-display rights",
        "reason": (
            "219 家公司跨美国、欧洲和亚洲交易所；全球供应商合同还须覆盖各交易所"
            "延迟/实时展示、历史存储、公司行为及币种统一，不以 Yahoo 作回退。"
        ),
        "proxy_description": (
            "免费阶段仅纳入已取得公开展示权的市场；其余公司显示财务和官方 IR "
            "链接，不生成合成 K 线或估值。"
        ),
        "priority": 1,
    },
    {
        "key": "global-company-fundamentals",
        "page_key": "ai-company",
        "metric_name": "非美公司标准化财务、公司行为与估值口径",
        "status": PURCHASE_REQUIRED,
        "vendor": "S&P Capital IQ-Compustat / FactSet Fundamentals / LSEG Fundamentals",
        "product": "Global fundamentals with storage, derived analytics and website-display rights",
        "reason": (
            "SEC Company Facts 只覆盖美国申报且标签口径不统一；全球横向比较需要"
            "标准化财务、拆股分红、币种和报告期映射的商业数据权利。"
        ),
        "proxy_description": (
            "人工解析公司 IR、交易所公告和当地官方申报，只展示已核验字段并保留"
            "原文链接；缺失字段留空，不用推测值补齐。"
        ),
        "priority": 2,
    },
    {
        "key": "analyst-estimates-ratings",
        "page_key": "ai-company",
        "metric_name": "一致预期、目标价与分析师评级",
        "status": PURCHASE_REQUIRED,
        "vendor": "S&P Capital IQ Estimates / FactSet Consensus / LSEG I-B-E-S",
        "product": "Consensus estimates and recommendations with external-display rights",
        "reason": (
            "一致预期、目标价和评级为贡献者及聚合商授权数据；终端查询权不等于"
            "可将逐公司历史和分析师明细发布到公共网站。"
        ),
        "proxy_description": (
            "只展示公司官方 guidance、实际财报和 Atlas 自有情景，明确标注非市场"
            "一致预期，不从媒体报道拼接共识。"
        ),
        "priority": 2,
    },
    {
        "key": "supply-chain-relationships",
        "page_key": "ai-industry-graph",
        "metric_name": "AI 供应链客户、供应商、产能与依赖关系",
        "status": PURCHASE_REQUIRED,
        "vendor": "FactSet Revere Supply Chain / S&P Business Relationships-Panjiva / Bloomberg Supply Chain",
        "product": "Entity-resolved supply-chain relationships with storage and public-derived-display rights",
        "reason": (
            "完整客户供应商网络、关系强度与历史变化是商业实体解析数据；采购时须确认"
            "是否可在公开图谱展示原始边、派生分数及供应商命名。"
        ),
        "proxy_description": (
            "自建关系库仅录入 SEC、公司 IR、交易所公告等明确披露的边，每条保存"
            "证据 URL、披露日期、关系类型、置信度和人工审核状态。"
        ),
        "priority": 1,
    },
    {
        "key": "model-benchmarks-pricing",
        "page_key": "model-evolution",
        "metric_name": "模型能力、价格与发布时间线",
        "status": PURCHASE_REQUIRED,
        "vendor": "Artificial Analysis Commercial / LMArena by written permission",
        "product": "Benchmark scores and history with API, archival and external-display rights",
        "reason": (
            "第三方模型榜的网页可见分数、排名和历史不等于可复制数据库；公开产品应"
            "采购 Artificial Analysis 商用授权，并就 LMArena 数据取得书面许可。"
        ),
        "proxy_description": (
            "可自行运行 SWE-bench、Terminal-Bench 等开放基准并公开方法、提交、环境"
            "和时间；模型价格与发布时间只取厂商官方文档，不混成第三方综合榜。"
        ),
        "priority": 2,
    },
    {
        "key": "model-vendor-metadata",
        "page_key": "model-evolution",
        "metric_name": "模型官方价格、上下文长度、发布日期与退役时间",
        "status": NEEDS_SOURCE,
        "source_name": "Model-provider official pricing, release and deprecation documentation",
        "reason": (
            "需建立官方链接白名单、字段口径、变更快照和人工复核；厂商文档可作为事实"
            "来源，但大段文案和品牌素材仍不可直接复制。"
        ),
        "priority": 2,
    },
    {
        "key": "github-project-radar",
        "page_key": "applications",
        "metric_name": "GitHub stars、forks、issues 与周增量",
        "status": NEEDS_SOURCE,
        "source_name": "GitHub REST API",
        "source_url": "https://docs.github.com/en/rest",
        "reason": (
            "API 可用，但当前合成仓库清单必须先替换为经审核的真实项目种子库；"
            "同时需保存每日快照、处理 rename/fork/archive，并遵守 attribution 和速率限制。"
        ),
        "priority": 2,
    },
    {
        "key": "daily-judgment-evidence",
        "page_key": "home",
        "metric_name": "今日判断、三项证据、触发器与证伪闭环",
        "status": NEEDS_SOURCE,
        "source_name": "Atlas Macro reviewed analysis over complete official/licensed batches",
        "reason": "真实研判必须引用可追溯 Observation/MetricSnapshot；演示日报已停止公开。",
        "priority": 1,
    },
    {
        "key": "trade-map-inputs",
        "page_key": "trade-map",
        "metric_name": "受益/回避资产、风险预算和跨资产确认矩阵",
        "status": PURCHASE_REQUIRED,
        "vendor": "Databento / Intrinio / licensed multi-asset provider",
        "product": "Cross-asset delayed/EOD display and derived-analytics licence",
        "reason": "交易地图依赖同批次股票、ETF、利率、商品和外汇价格，不能由静态观点填充。",
        "priority": 1,
    },
    {
        "key": "etf-holdings-flows",
        "page_key": "assets-etfs",
        "metric_name": "ETF 行情、AUM、持仓与申赎资金流",
        "status": PURCHASE_REQUIRED,
        "vendor": "FactSet Funds / LSEG Lipper / licensed issuer feeds",
        "product": "ETF prices, holdings, AUM and flows with public-display rights",
        "reason": "行情、持仓、AUM 与 Flow 是不同授权范围，需逐项确认。",
        "priority": 1,
    },
    {
        "key": "bond-market-prices",
        "page_key": "assets-bonds",
        "metric_name": "国债与信用债价格、久期和总回报",
        "status": PURCHASE_REQUIRED,
        "vendor": "FINRA TRACE / LSEG / Bloomberg / FactSet",
        "product": "Fixed-income pricing and public-display licence",
        "reason": "财政部收益率曲线可免费使用，但不能替代债券/ETF 可交易价格与总回报。",
        "priority": 2,
    },
    {
        "key": "fx-market-data",
        "page_key": "assets-fx",
        "metric_name": "主要货币现货、远期点与美元指数",
        "status": PURCHASE_REQUIRED,
        "vendor": "CME EBS / Cboe FX / LSEG / ICE for DXY",
        "product": "FX spot, forwards and branded-index display rights",
        "reason": "FX 无统一官方 tape，DXY 与远期/基差需独立授权。",
        "proxy_description": "Fed H.10 或央行参考汇率可作为日频现货代理并清晰标注。",
        "priority": 2,
    },
    {
        "key": "liquidity-transmission-inputs",
        "page_key": "transmission-chain",
        "metric_name": "六层流动性传导链完整输入",
        "status": NEEDS_SOURCE,
        "source_name": "NY Fed, Federal Reserve H.4.1, Treasury plus licensed FX/volatility/credit inputs",
        "reason": "SOFR/EFFR 已接入，但离岸基差、AOCI、中介能力与资产反应仍缺授权输入。",
        "priority": 1,
    },
    {
        "key": "nyfed-market-operations",
        "page_key": "operations",
        "metric_name": "Repo/RRP 操作、SRF 与 SOMA 明细",
        "status": NEEDS_SOURCE,
        "source_name": "Federal Reserve Bank of New York Markets API",
        "source_url": "https://markets.newyorkfed.org/static/docs/markets-api.html",
        "reason": "官方端点已确认，尚待规范化操作类型、结算日、金额和修订。",
        "priority": 1,
    },
    {
        "key": "fed-reserve-balances",
        "page_key": "reserves",
        "metric_name": "准备金余额、占银行资产比例与充裕度",
        "status": NEEDS_SOURCE,
        "source_name": "Federal Reserve H.4.1 Data Download Program",
        "source_url": "https://www.federalreserve.gov/datadownload/Choose.aspx?rel=H41",
        "reason": "需直接规范化 WRESBAL 与银行资产分母，不能继续使用演示序列。",
        "priority": 1,
    },
    {
        "key": "sofr-distribution-volume",
        "page_key": "subsurface",
        "metric_name": "SOFR 分位、成交量和尾部融资压力",
        "status": NEEDS_SOURCE,
        "source_name": "Federal Reserve Bank of New York Markets API",
        "source_url": "https://markets.newyorkfed.org/static/docs/markets-api.html",
        "reason": "基础记录已入库，尚待分位差、Z-score、SRF 激活和历史图的专页快照。",
        "priority": 1,
    },
    {
        "key": "move-page-data",
        "page_key": "volatility-move",
        "metric_name": "MOVE 指数历史、分位与期限分量",
        "status": PURCHASE_REQUIRED,
        "vendor": "ICE Data Indices",
        "product": "ICE MOVE delayed/EOD/history with public-display rights",
        "reason": "MOVE 为 ICE 指数，网页可见或经 FRED 提供均不授予 Atlas 再分发权。",
        "priority": 1,
    },
    {
        "key": "fx-vol-surface",
        "page_key": "fx-vol",
        "metric_name": "FX ATM IV、25Δ Risk Reversal 与 Butterfly",
        "status": PURCHASE_REQUIRED,
        "vendor": "LSEG / Bloomberg / CME FX-CVOL",
        "product": "FX option volatility surface and external display",
        "reason": "主要货币期权波动率面为 OTC/交易所商业数据。",
        "priority": 1,
    },
    {
        "key": "iv-rv-cross-asset",
        "page_key": "implied-vs-realized",
        "metric_name": "跨资产隐含与实现波动率风险溢价",
        "status": PURCHASE_REQUIRED,
        "vendor": "Cboe/OPRA plus licensed underlying bars",
        "product": "Options IV and underlying history with derived-display rights",
        "reason": "IV 与标的历史必须同批次并具备派生公开展示许可。",
        "priority": 1,
    },
    {
        "key": "credit-stress-inputs",
        "page_key": "credit-stress",
        "metric_name": "信用压力五分量与历史回测",
        "status": PURCHASE_REQUIRED,
        "vendor": "ICE Data Indices / licensed TRACE provider plus official SLOOS",
        "product": "Credit spread history and derived stress-score display rights",
        "reason": "无 ICE/TRACE 授权时不能发布静态 OAS 水位或压力分数。",
        "priority": 2,
    },
    {
        "key": "supply-chain-public-evidence",
        "page_key": "supply-chain",
        "metric_name": "五环节供应链事件、产能与证据链",
        "status": NEEDS_SOURCE,
        "source_name": "Company IR, SEC, exchange filings and manually reviewed evidence",
        "reason": "先建立可追溯公开披露库；完整产能与客户分配再采购专业研究源。",
        "priority": 1,
    },
    {
        "key": "foundry-capacity",
        "page_key": "supply-chain-foundry",
        "metric_name": "先进制程产能、利用率和工厂爬坡",
        "status": PURCHASE_REQUIRED,
        "vendor": "TrendForce / TechInsights / Omdia",
        "product": "Foundry capacity estimates with public-derived-display rights",
        "reason": "公司披露可补路线图和 CapEx，月度利用率和市占率需专业授权。",
        "priority": 1,
    },
    {
        "key": "advanced-packaging-capacity",
        "page_key": "supply-chain-packaging",
        "metric_name": "CoWoS/SoIC/OSAT 产能、良率与供需缺口",
        "status": PURCHASE_REQUIRED,
        "vendor": "SemiAnalysis / TrendForce / TechInsights",
        "product": "Advanced-packaging capacity model and display licence",
        "reason": "精确月产能、良率和客户分配通常不由公司完整披露。",
        "priority": 1,
    },
    {
        "key": "hbm-supply-demand",
        "page_key": "supply-chain-hbm",
        "metric_name": "HBM 位产出、认证、价格与供需覆盖",
        "status": PURCHASE_REQUIRED,
        "vendor": "TrendForce / Omdia / TechInsights / SemiAnalysis",
        "product": "HBM supply-demand and pricing with public-display rights",
        "reason": "厂商公告可补里程碑，位产出、合约价和客户分配需专业授权。",
        "priority": 1,
    },
    {
        "key": "accelerator-shipments",
        "page_key": "supply-chain-gpu",
        "metric_name": "GPU/ASIC 出货、ASP、交付周期与客户部署",
        "status": PURCHASE_REQUIRED,
        "vendor": "SemiAnalysis Accelerator Model / Omdia / TechInsights",
        "product": "Accelerator shipments and installed-base display rights",
        "reason": "产品规格可来自厂商，出货和客户级安装基数属于估算数据。",
        "priority": 1,
    },
    {
        "key": "ai-demand-capex",
        "page_key": "supply-chain-demand",
        "metric_name": "云厂商 AI CapEx、算力部署与变现效率",
        "status": NEEDS_SOURCE,
        "source_name": "SEC filings and company investor-relations disclosures",
        "reason": "先规范化官方 CapEx/指引；未披露的 AI 拆分与 GPU 数量不得自行填充。",
        "priority": 1,
    },
    {
        "key": "ai-teardown-bom",
        "page_key": "ai-teardown",
        "metric_name": "AI 系统 BOM、价值量假设和版本化情景",
        "status": PURCHASE_REQUIRED,
        "vendor": "TechInsights / SemiAnalysis plus vendor BOM evidence",
        "product": "System teardown/BOM model with derived public-display rights",
        "reason": "原有百分比为演示值，已停止发布；每项成本和占比必须带来源及假设版本。",
        "priority": 1,
    },
]
