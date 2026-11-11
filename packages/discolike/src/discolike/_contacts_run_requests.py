# Hand-maintained against platform contacts_run.py; do not regenerate from older deployed specs.

from __future__ import annotations

from decimal import Decimal
from typing import Annotated
from typing import Literal

from pydantic import AwareDatetime
from pydantic import ConfigDict
from pydantic import Field

from discolike._models import DiscolikeRequest


class TitlePreviewRequest(DiscolikeRequest):
    titles: Annotated[list[str], Field(max_length=50, min_length=1, title="Titles")]
    exclude_titles: Annotated[list[str] | None, Field(title="Exclude Titles")] = None
    match: Annotated[Literal["similar", "exact"], Field(title="Match")]
    relevance: Literal["max_relevance", "balanced", "max_coverage"] = "balanced"
    auto_stop: bool = True


class DomainCompanies(DiscolikeRequest):
    source: Annotated[Literal["domains"], Field(title="Source")]
    domains: Annotated[
        list[str],
        Field(description="Company domains to find contacts at.", max_length=10000, min_length=1, title="Domains"),
    ]
    scores: Annotated[
        dict[str, float] | None,
        Field(description="Optional relevance score per domain, keyed by domain.", title="Scores"),
    ] = None


class LookalikeCompanies(DiscolikeRequest):
    source: Annotated[Literal["lookalike"], Field(title="Source")]
    persona_ids: Annotated[
        list[int],
        Field(description="Personas whose companies seed the lookalike search.", min_length=1, title="Persona Ids"),
    ]


class ContactsPeopleFit(DiscolikeRequest):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    fit: str = Field(default="Senior executives and decision makers", min_length=1, max_length=4000)


class PromptCompanyFilters(DiscolikeRequest):
    filter_industry: Annotated[
        list[
            Literal[
                "ACCOUNTING",
                "ADVERTISING_AND_MARKETING",
                "AGRICULTURE_AND_NATURAL_RESOURCES",
                "ALCOHOL_AND_TOBACCO",
                "AUTOMOTIVE",
                "BIG_DATA_AND_ANALYTICS",
                "BIOTECHNOLOGY",
                "BLOCKCHAIN_AND_CRYPTOCURRENCY",
                "BUSINESS_PRODUCTS_AND_SERVICES",
                "CLOUD_COMPUTING",
                "COMPUTER_HARDWARE_AND_SEMICONDUCTORS",
                "CONGLOMERATES_SHELL_AND_HOLDING_COMPANIES",
                "CONSTRUCTION",
                "CONSUMER_PRODUCTS",
                "CONSUMER_SERVICES",
                "CYBERSECURITY",
                "DEFENSE_AND_AEROSPACE",
                "E-COMMERCE",
                "EDUCATION",
                "ENERGY",
                "ENGINEERING",
                "ENTERTAINMENT",
                "ENVIRONMENTAL_SERVICES",
                "FASHION_TEXTILE_AND_APPAREL",
                "FINANCIAL_SERVICES",
                "FOOD_AND_BEVERAGE",
                "GAMING_AND_ESPORTS",
                "GOVERNMENT_SERVICES",
                "HEALTHCARE",
                "HOSPITALITY",
                "HUMAN_RESOURCES",
                "INSURANCE",
                "IT_SERVICES",
                "LEGAL",
                "MANUFACTURING",
                "MEDIA",
                "MINING_AND_METALS",
                "NONPROFIT_AND_PHILANTHROPY",
                "OIL_AND_GAS",
                "PHARMACEUTICALS",
                "PRIVATE_EQUITY_AND_VENTURE_CAPITAL",
                "REAL_ESTATE",
                "RENEWABLE_ENERGY",
                "RESTAURANTS",
                "RETAIL",
                "SAAS",
                "SECURITY",
                "SOFTWARE",
                "SPORTS_AND_RECREATION",
                "SUPPLY_CHAIN_AND_PROCUREMENT",
                "TELECOMMUNICATIONS",
                "TRAVEL",
                "WELLNESS_AND_LIFESTYLE",
            ]
        ]
        | None,
        Field(
            description="Filter by industry category. Valid values: ACCOUNTING, ADVERTISING_AND_MARKETING, AGRICULTURE_AND_NATURAL_RESOURCES, ALCOHOL_AND_TOBACCO, AUTOMOTIVE, BIG_DATA_AND_ANALYTICS, BIOTECHNOLOGY, BLOCKCHAIN_AND_CRYPTOCURRENCY, BUSINESS_PRODUCTS_AND_SERVICES, CLOUD_COMPUTING, COMPUTER_HARDWARE_AND_SEMICONDUCTORS, CONGLOMERATES_SHELL_AND_HOLDING_COMPANIES, CONSTRUCTION, CONSUMER_PRODUCTS, CONSUMER_SERVICES, CYBERSECURITY, DEFENSE_AND_AEROSPACE, E-COMMERCE, EDUCATION, ENERGY, ENGINEERING, ENTERTAINMENT, ENVIRONMENTAL_SERVICES, FASHION_TEXTILE_AND_APPAREL, FINANCIAL_SERVICES, FOOD_AND_BEVERAGE, GAMING_AND_ESPORTS, GOVERNMENT_SERVICES, HEALTHCARE, HOSPITALITY, HUMAN_RESOURCES, INSURANCE, IT_SERVICES, LEGAL, MANUFACTURING, MEDIA, MINING_AND_METALS, NONPROFIT_AND_PHILANTHROPY, OIL_AND_GAS, PHARMACEUTICALS, PRIVATE_EQUITY_AND_VENTURE_CAPITAL, REAL_ESTATE, RENEWABLE_ENERGY, RESTAURANTS, RETAIL, SAAS, SECURITY, SOFTWARE, SPORTS_AND_RECREATION, SUPPLY_CHAIN_AND_PROCUREMENT, TELECOMMUNICATIONS, TRAVEL, WELLNESS_AND_LIFESTYLE.",
            title="Filter Industry",
        ),
    ] = None
    negate_filter_industry: Annotated[
        list[
            Literal[
                "ACCOUNTING",
                "ADVERTISING_AND_MARKETING",
                "AGRICULTURE_AND_NATURAL_RESOURCES",
                "ALCOHOL_AND_TOBACCO",
                "AUTOMOTIVE",
                "BIG_DATA_AND_ANALYTICS",
                "BIOTECHNOLOGY",
                "BLOCKCHAIN_AND_CRYPTOCURRENCY",
                "BUSINESS_PRODUCTS_AND_SERVICES",
                "CLOUD_COMPUTING",
                "COMPUTER_HARDWARE_AND_SEMICONDUCTORS",
                "CONGLOMERATES_SHELL_AND_HOLDING_COMPANIES",
                "CONSTRUCTION",
                "CONSUMER_PRODUCTS",
                "CONSUMER_SERVICES",
                "CYBERSECURITY",
                "DEFENSE_AND_AEROSPACE",
                "E-COMMERCE",
                "EDUCATION",
                "ENERGY",
                "ENGINEERING",
                "ENTERTAINMENT",
                "ENVIRONMENTAL_SERVICES",
                "FASHION_TEXTILE_AND_APPAREL",
                "FINANCIAL_SERVICES",
                "FOOD_AND_BEVERAGE",
                "GAMING_AND_ESPORTS",
                "GOVERNMENT_SERVICES",
                "HEALTHCARE",
                "HOSPITALITY",
                "HUMAN_RESOURCES",
                "INSURANCE",
                "IT_SERVICES",
                "LEGAL",
                "MANUFACTURING",
                "MEDIA",
                "MINING_AND_METALS",
                "NONPROFIT_AND_PHILANTHROPY",
                "OIL_AND_GAS",
                "PHARMACEUTICALS",
                "PRIVATE_EQUITY_AND_VENTURE_CAPITAL",
                "REAL_ESTATE",
                "RENEWABLE_ENERGY",
                "RESTAURANTS",
                "RETAIL",
                "SAAS",
                "SECURITY",
                "SOFTWARE",
                "SPORTS_AND_RECREATION",
                "SUPPLY_CHAIN_AND_PROCUREMENT",
                "TELECOMMUNICATIONS",
                "TRAVEL",
                "WELLNESS_AND_LIFESTYLE",
            ]
        ]
        | None,
        Field(
            description="Exclude contacts at companies in specified industries. Valid values: ACCOUNTING, ADVERTISING_AND_MARKETING, AGRICULTURE_AND_NATURAL_RESOURCES, ALCOHOL_AND_TOBACCO, AUTOMOTIVE, BIG_DATA_AND_ANALYTICS, BIOTECHNOLOGY, BLOCKCHAIN_AND_CRYPTOCURRENCY, BUSINESS_PRODUCTS_AND_SERVICES, CLOUD_COMPUTING, COMPUTER_HARDWARE_AND_SEMICONDUCTORS, CONGLOMERATES_SHELL_AND_HOLDING_COMPANIES, CONSTRUCTION, CONSUMER_PRODUCTS, CONSUMER_SERVICES, CYBERSECURITY, DEFENSE_AND_AEROSPACE, E-COMMERCE, EDUCATION, ENERGY, ENGINEERING, ENTERTAINMENT, ENVIRONMENTAL_SERVICES, FASHION_TEXTILE_AND_APPAREL, FINANCIAL_SERVICES, FOOD_AND_BEVERAGE, GAMING_AND_ESPORTS, GOVERNMENT_SERVICES, HEALTHCARE, HOSPITALITY, HUMAN_RESOURCES, INSURANCE, IT_SERVICES, LEGAL, MANUFACTURING, MEDIA, MINING_AND_METALS, NONPROFIT_AND_PHILANTHROPY, OIL_AND_GAS, PHARMACEUTICALS, PRIVATE_EQUITY_AND_VENTURE_CAPITAL, REAL_ESTATE, RENEWABLE_ENERGY, RESTAURANTS, RETAIL, SAAS, SECURITY, SOFTWARE, SPORTS_AND_RECREATION, SUPPLY_CHAIN_AND_PROCUREMENT, TELECOMMUNICATIONS, TRAVEL, WELLNESS_AND_LIFESTYLE.",
            title="Negate Filter Industry",
        ),
    ] = None
    filter_country: Annotated[
        list[str] | None,
        Field(
            description="Filter by company country using ISO-3166-1 alpha-2 codes (e.g., US, GB, DE). Also accepts region aliases: EU, LATAM, MENA, APAC, NORDICS, DACH, BENELUX, GCC, ASEAN, CEE, ANZ, EUROPE, ASIA, AFRICA, NORTH_AMERICA, SOUTH_AMERICA, OCEANIA, ANTARCTICA.",
            title="Filter Country",
        ),
    ] = None
    negate_filter_country: Annotated[
        list[str] | None,
        Field(
            description="Exclude contacts at companies in specified countries. Accepts same codes and region aliases as filter_country.",
            title="Negate Filter Country",
        ),
    ] = None
    filter_state: Annotated[
        list[str] | None,
        Field(
            description="Filter by company state/region. Accepts ISO 3166-2 codes or names, listed at https://docs.discolike.com/states/, resolved against the selected countries; a value that resolves under none is ignored.",
            title="Filter State",
        ),
    ] = None
    negate_filter_state: Annotated[
        list[str] | None,
        Field(
            description="Exclude contacts at companies in specified states. Same format as filter_state.",
            title="Negate Filter State",
        ),
    ] = None
    employee_range: Annotated[
        str | None,
        Field(
            description="Filter by employee count range. Format: 'min,max' (e.g., '51,200'). Maps to buckets: 1-10, 11-50, 51-200, 201-500, 501-1000, 1001-5000, 5001-10000, 10001+.",
            title="Employee Range",
        ),
    ] = None
    revenue_range: Annotated[
        str | None,
        Field(
            description="Company revenue range as 'min,max' in raw numbers, e.g. '10000000,50000000'.",
            title="Revenue Range",
        ),
    ] = None
    sub_industry: Annotated[
        list[str] | None,
        Field(
            description="Only include companies in these sub-industries. Accepts a parent-qualified key (CONSTRUCTION/ROOFING), or a bare label (ROOFING) whose parent is unambiguous, case-insensitive.",
            title="Sub Industry",
        ),
    ] = None


class ContinueRunRequest(DiscolikeRequest):
    model_config = ConfigDict(extra="forbid")

    generation: int
    redo: bool = False


class PromptCompanies(DiscolikeRequest):
    source: Literal["prompt"]
    icp_text: str | None = Field(default=None, min_length=3)
    filters: PromptCompanyFilters = Field(default_factory=PromptCompanyFilters)


class ContactsRunRequest(DiscolikeRequest):
    model_config = ConfigDict(extra="forbid")

    companies: Annotated[PromptCompanies | DomainCompanies | LookalikeCompanies, Field(discriminator="source")]
    people: ContactsPeopleFit = Field(default_factory=ContactsPeopleFit)
    relevance: Literal["max_relevance", "balanced", "max_coverage"] = "balanced"
    max_companies: int = Field(default=500, ge=1, le=10000)
    per_company: int = Field(default=10, ge=1, le=50)
    email_cap_usd: Decimal | None = Field(default=None, ge=0)
    exclude_query_ids: list[str] = Field(default_factory=list, max_length=20)
    exclude_domains: list[str] = Field(default_factory=list, max_length=100)
    create_key: str | None = None


class ContactsRunEventsParams(DiscolikeRequest):
    after: int = Field(default=0, ge=0)
    limit: int = Field(default=100, ge=1, le=500)


class ContactsRunListParams(DiscolikeRequest):
    before: Annotated[AwareDatetime | None, Field(title="Before")] = None
    limit: Annotated[int | None, Field(ge=1, le=100, title="Limit")] = 20


class ContactsRunGetParams(DiscolikeRequest):
    rows_offset: Annotated[int | None, Field(ge=0, title="Rows Offset")] = 0
    rows_limit: Annotated[int | None, Field(ge=1, le=1000, title="Rows Limit")] = 100
