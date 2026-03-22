from typing import TypedDict, List, Dict, Any

class Clause(TypedDict):
    clause_id: str
    title: str
    text: str
    section_number: str

class Rule(TypedDict):
    rule_id: str
    citation: str
    text: str
    relevance_score: float

class ClauseAnalysis(TypedDict):
    clause_id: str
    compliance_status: str
    risk_level: str
    issues: List[Dict[str, Any]]

class GraphState(TypedDict):
    document_id: str
    raw_text: str
    clauses: List[Clause]
    analyses: List[ClauseAnalysis]
    audit_log: List[str]
    summary: Dict[str, Any]
