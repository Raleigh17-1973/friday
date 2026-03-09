from business_ai.agents.communications import CommunicationsAgent
from business_ai.agents.generic_domain import GenericDomainAgent


def build_agents() -> dict[str, object]:
    return {
        "sales": GenericDomainAgent("sales", "revenue growth and pipeline execution"),
        "customer_support": GenericDomainAgent("customer_support", "customer issue triage and SLA execution"),
        "hr": GenericDomainAgent("hr", "people operations and adoption"),
        "corporate_it": GenericDomainAgent("corporate_it", "internal IT operations and access"),
        "engineering": GenericDomainAgent("engineering", "technical delivery and reliability"),
        "finance": GenericDomainAgent("finance", "business case economics and controls"),
        "grc": GenericDomainAgent("grc", "governance, risk, and compliance"),
        "legal": GenericDomainAgent("legal", "contractual and legal risk"),
        "strategy": GenericDomainAgent("strategy", "strategic choices and scenarios"),
        "product": GenericDomainAgent("product", "product scope and roadmap"),
        "pmo": GenericDomainAgent("pmo", "program governance and delivery management"),
        "data_analytics": GenericDomainAgent("data_analytics", "metrics, analytics, and experimentation"),
        "security": GenericDomainAgent("security", "threat and control response"),
        "procurement_vendor": GenericDomainAgent("procurement_vendor", "vendor strategy and sourcing"),
        "operations": GenericDomainAgent("operations", "process performance and throughput"),
        "revenue_operations": GenericDomainAgent("revenue_operations", "funnel and forecast operations"),
        "executive_cos": GenericDomainAgent("executive_cos", "executive decision support"),
        "qa_critic": GenericDomainAgent("qa_critic", "assumption challenge and risk critique"),
        "communications": CommunicationsAgent(),
    }
