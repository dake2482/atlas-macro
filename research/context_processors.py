from django.conf import settings

NAV_GROUPS = [
    {
        "label": "核心入口",
        "items": [
            ("今日判断", "/"),
            ("市场仪表盘", "/assets/"),
            ("每日报告", "/daily-report/"),
            ("研究库", "/research/reports/"),
            ("基金信函", "/research/fund-letters/"),
            ("AI 资本地图", "/ai-industry/market-map/"),
            ("新闻 / 事件", "/news/"),
        ],
    },
    {
        "label": "大类资产",
        "root": "/assets/",
        "items": [
            ("总览", "/assets/"),
            ("美股", "/assets/equities/"),
            ("ETF 看板", "/assets/etfs/"),
            ("期权 / GEX", "/assets/equities/options/"),
            ("CFTC 持仓", "/assets/equities/positioning/"),
            ("债券", "/assets/bonds/"),
            ("商品", "/assets/commodities/"),
            ("外汇", "/assets/fx/"),
            ("加密货币", "/assets/crypto/"),
            ("加密衍生品", "/assets/crypto/derivatives/"),
        ],
    },
    {
        "label": "利率",
        "root": "/rates/",
        "items": [
            ("总览", "/rates/"),
            ("联邦基金利率", "/rates/fed-funds/"),
            ("收益率曲线", "/rates/yield-curve/"),
            ("国债拍卖", "/rates/auctions/"),
            ("实际利率", "/rates/real-rates/"),
            ("利率预期", "/rates/expectations/"),
        ],
    },
    {
        "label": "美联储",
        "root": "/fed/",
        "items": [
            ("总览", "/fed/"),
            ("FOMC 声明", "/fed/statements/"),
            ("官员演讲", "/fed/speeches/"),
            ("联储公告", "/fed/news/"),
            ("鹰鸽追踪", "/fed/hawkish-dovish/"),
        ],
    },
    {
        "label": "流动性",
        "root": "/liquidity/",
        "items": [
            ("总览", "/liquidity/"),
            ("六层传导链", "/liquidity/transmission-chain/"),
            ("资产负债表", "/liquidity/fed-balance-sheet/"),
            ("公开市场操作", "/liquidity/operations/"),
            ("RRP & TGA", "/liquidity/rrp-tga/"),
            ("准备金", "/liquidity/reserves/"),
            ("全球美元", "/liquidity/global-dollar/"),
            ("次表层资金流", "/liquidity/subsurface/"),
        ],
    },
    {
        "label": "经济 / 风险",
        "items": [
            ("经济总览", "/economy/"),
            ("GDP", "/economy/gdp/"),
            ("就业", "/economy/employment/"),
            ("通胀", "/economy/inflation/"),
            ("消费", "/economy/consumer/"),
            ("波动率", "/volatility/"),
            ("信用市场", "/credit/"),
        ],
    },
    {
        "label": "AI 产业观察",
        "root": "/ai-industry/",
        "items": [
            ("总览", "/ai-industry/"),
            ("资本地图", "/ai-industry/market-map/"),
            ("关系图谱", "/ai-industry/graph/"),
            ("AI 资讯", "/ai-industry/news/"),
            ("产业链", "/ai-industry/chain/"),
            ("大模型演变", "/ai-industry/chain/model-evolution/"),
            ("AI 应用", "/ai-industry/chain/applications/"),
            ("专业术语", "/ai-industry/chain/glossary/"),
        ],
    },
]


def site_context(request):
    return {
        "site_name": settings.SITE_NAME,
        "site_url": settings.SITE_URL,
        "nav_groups": NAV_GROUPS,
        "current_path": request.path,
    }

