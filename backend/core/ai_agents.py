# core/ai_agents.py - Enhanced AI Agent System
import json
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class AgentType(Enum):
    DOCUMENT_ANALYZER = "document_analyzer"
    RISK_ASSESSOR = "risk_assessor"
    ORACLE_MAPPER = "oracle_mapper"
    PLANNING_ADVISOR = "planning_advisor"
    COMPLIANCE_CHECKER = "compliance_checker"
    OPTIMIZATION_ADVISOR = "optimization_advisor"
    DATA_EXTRACTOR = "data_extractor"
    REPORT_GENERATOR = "report_generator"

class AnalysisApproach(Enum):
    COMPREHENSIVE = "comprehensive"  # All agents
    QUICK_SCAN = "quick_scan"       # Essential agents only
    RISK_FOCUSED = "risk_focused"   # Risk and compliance focus
    TECHNICAL_MAPPING = "technical_mapping"  # Oracle ICM focus
    CUSTOM = "custom"               # User-selected agents

@dataclass
class AgentResult:
    agent_name: str
    status: str  # success, failed, partial
    execution_time: float
    confidence_score: float
    data: Dict[str, Any]
    errors: List[str] = None
    warnings: List[str] = None

class BaseAgent:
    """Base class for all AI agents"""
    
    def __init__(self, name: str, description: str, model_preferences: List[str]):
        self.name = name
        self.description = description
        self.model_preferences = model_preferences
        self.execution_count = 0
        self.success_rate = 0.0
    
    async def execute(self, inputs: Dict[str, Any], context: Dict[str, Any] = None) -> AgentResult:
        """Execute the agent with given inputs"""
        start_time = datetime.now()
        
        try:
            result_data = await self._process(inputs, context or {})
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # Calculate confidence based on result completeness
            confidence = self._calculate_confidence(result_data)
            
            self.execution_count += 1
            self.success_rate = (self.success_rate * (self.execution_count - 1) + 1.0) / self.execution_count
            
            return AgentResult(
                agent_name=self.name,
                status="success",
                execution_time=execution_time,
                confidence_score=confidence,
                data=result_data
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"Agent {self.name} failed: {str(e)}")
            
            return AgentResult(
                agent_name=self.name,
                status="failed",
                execution_time=execution_time,
                confidence_score=0.0,
                data={},
                errors=[str(e)]
            )
    
    async def _process(self, inputs: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Override this method in each agent"""
        raise NotImplementedError
    
    def _calculate_confidence(self, result_data: Dict[str, Any]) -> float:
        """Calculate confidence score based on result completeness"""
        if not result_data:
            return 0.0
        
        # Basic scoring - can be enhanced per agent
        required_fields = self._get_required_fields()
        present_fields = sum(1 for field in required_fields if field in result_data and result_data[field])
        
        return present_fields / len(required_fields) if required_fields else 1.0
    
    def _get_required_fields(self) -> List[str]:
        """Override to define required output fields"""
        return []

class DocumentAnalyzerAgent(BaseAgent):
    """Specialized agent for document analysis and structure extraction"""
    
    def __init__(self):
        super().__init__(
            name="Document Analyzer",
            description="Extracts and structures compensation plan information from documents",
            model_preferences=["gpt-4", "claude-3-sonnet", "gpt-3.5-turbo"]
        )
    
    async def _process(self, inputs: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        text = inputs.get("text", "")
        template = inputs.get("template", "master")
        
        prompt = self._build_prompt(text, template)
        
        # Call LLM (using existing infrastructure)
        from .prompting import call_llm
        result = call_llm(prompt)
        
        try:
            parsed_result = json.loads(result)
            return self._enhance_document_analysis(parsed_result, text)
        except json.JSONDecodeError:
            # Fallback parsing
            return self._fallback_parse(result, text)
    
    def _build_prompt(self, text: str, template: str) -> str:
        return f"""
        You are a specialized Document Analysis Agent for compensation plans.
        
        Your task: Extract and structure ALL relevant information from the document.
        
        Focus on:
        1. Plan Structure: eligibility, timing, calculations
        2. Key Metrics: quotas, rates, thresholds
        3. Business Rules: conditions, exceptions, overrides
        4. Data Requirements: inputs, integrations, reports
        5. Stakeholder Information: roles, responsibilities
        
        Template Context: {template}
        
        Document Text:
        <<<
        {text[:50000]}  # Truncate for model limits
        >>>
        
        Return comprehensive JSON with:
        {{
            "plan_overview": {{"name": "", "type": "", "summary": ""}},
            "plan_structure": [
                {{"component": "", "description": "", "calculation_method": "", "dependencies": []}}
            ],
            "eligibility_criteria": [
                {{"role": "", "requirements": [], "effective_dates": ""}}
            ],
            "calculation_rules": [
                {{"rule_name": "", "formula": "", "conditions": [], "examples": []}}
            ],
            "key_metrics": [
                {{"metric": "", "target": "", "measurement": "", "frequency": ""}}
            ],
            "data_requirements": [
                {{"data_type": "", "source": "", "frequency": "", "format": ""}}
            ],
            "business_rules": [
                {{"rule": "", "condition": "", "action": "", "priority": ""}}
            ],
            "governance": [
                {{"aspect": "", "requirement": "", "owner": "", "frequency": ""}}
            ]
        }}
        """
    
    def _enhance_document_analysis(self, parsed_result: Dict, original_text: str) -> Dict[str, Any]:
        """Enhance the basic analysis with additional insights"""
        enhanced = parsed_result.copy()
        
        # Add document metadata
        enhanced["document_metadata"] = {
            "length": len(original_text),
            "complexity_score": self._calculate_complexity(original_text),
            "key_terms_found": self._extract_key_terms(original_text),
            "analysis_timestamp": datetime.now().isoformat()
        }
        
        # Add confidence indicators
        enhanced["confidence_indicators"] = {
            "calculation_clarity": self._assess_calculation_clarity(parsed_result),
            "completeness_score": self._assess_completeness(parsed_result),
            "consistency_score": self._assess_consistency(parsed_result)
        }
        
        return enhanced
    
    def _calculate_complexity(self, text: str) -> float:
        """Calculate document complexity score"""
        complexity_indicators = [
            "if", "when", "unless", "except", "override", "special", "complex",
            "variable", "depends", "conditional", "multiple", "various"
        ]
        
        score = sum(text.lower().count(indicator) for indicator in complexity_indicators)
        return min(score / 100.0, 1.0)  # Normalize to 0-1
    
    def _extract_key_terms(self, text: str) -> List[str]:
        """Extract key compensation terms"""
        key_terms = [
            "commission", "bonus", "incentive", "quota", "target", "threshold",
            "rate", "tier", "accelerator", "kicker", "spiff", "draw", "clawback"
        ]
        
        found_terms = []
        text_lower = text.lower()
        for term in key_terms:
            if term in text_lower:
                found_terms.append(term)

        return found_terms

    def _assess_calculation_clarity(self, result: Dict[str, Any]) -> float:
        """Assess clarity of calculation rules"""
        rules = result.get("calculation_rules", [])
        if not rules:
            return 0.0

        clear_rules = 0
        for rule in rules:
            if rule.get("formula") and rule.get("examples"):
                clear_rules += 1

        return clear_rules / len(rules)

    def _assess_completeness(self, result: Dict[str, Any]) -> float:
        """Assess completeness of analysis"""
        required = self._get_required_fields()
        if not required:
            return 1.0

        present = sum(1 for field in required if field in result and result[field])
        return present / len(required)

    def _assess_consistency(self, result: Dict[str, Any]) -> float:
        """Assess consistency between plan structure and calculation rules"""
        structures = result.get("plan_structure", [])
        rules = result.get("calculation_rules", [])
        if not structures or not rules:
            return 0.0

        components = {s.get("component") for s in structures if s.get("component")}
        rule_names = {r.get("rule_name") for r in rules if r.get("rule_name")}
        if not components:
            return 0.0

        matches = components.intersection(rule_names)
        return len(matches) / len(components)
    
    def _get_required_fields(self) -> List[str]:
        return ["plan_structure", "calculation_rules", "eligibility_criteria"]

class RiskAssessmentAgent(BaseAgent):
    """Specialized agent for identifying risks and compliance issues"""
    
    def __init__(self):
        super().__init__(
            name="Risk Assessment",
            description="Identifies compliance, operational, and financial risks in compensation plans",
            model_preferences=["claude-3-sonnet", "gpt-4", "gpt-3.5-turbo"]
        )
    
    async def _process(self, inputs: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        plan_data = inputs.get("plan_data", {})
        industry = context.get("industry", "general")
        region = context.get("region", "US")
        
        prompt = self._build_risk_prompt(plan_data, industry, region)

        from .prompting import call_llm
        result = call_llm(prompt)
        
        try:
            parsed_result = json.loads(result)
            return self._enhance_risk_analysis(parsed_result, plan_data)
        except json.JSONDecodeError:
            return self._fallback_risk_analysis(result)
    
    def _build_risk_prompt(self, plan_data: Dict, industry: str, region: str) -> str:
        return f"""
        You are a Risk Assessment Specialist for compensation plans.
        
        Analyze the following plan for ALL types of risks:
        
        1. COMPLIANCE RISKS:
           - Regulatory violations (SOX, securities laws)
           - Tax implications
           - Labor law compliance
           - Industry-specific regulations
        
        2. OPERATIONAL RISKS:
           - Data accuracy dependencies
           - System integration complexity
           - Manual calculation risks
           - Reporting and audit trails
        
        3. FINANCIAL RISKS:
           - Budget overruns
           - Calculation errors
           - Gaming/manipulation potential
           - Cash flow impacts
        
        4. STRATEGIC RISKS:
           - Misaligned incentives
           - Unintended behaviors
           - Competitive disadvantage
           - Talent retention issues
        
        Plan Data: {json.dumps(plan_data, indent=2)}
        Industry: {industry}
        Region: {region}
        
        Return detailed JSON:
        {{
            "compliance_risks": [
                {{
                    "risk_type": "regulatory|tax|labor|industry",
                    "description": "",
                    "severity": "low|medium|high|critical",
                    "probability": "low|medium|high",
                    "impact": "",
                    "mitigation_strategies": [],
                    "regulatory_references": []
                }}
            ],
            "operational_risks": [
                {{
                    "risk_type": "data|integration|manual|reporting",
                    "description": "",
                    "severity": "low|medium|high|critical",
                    "probability": "low|medium|high",
                    "impact": "",
                    "mitigation_strategies": [],
                    "automation_opportunities": []
                }}
            ],
            "financial_risks": [
                {{
                    "risk_type": "budget|calculation|gaming|cashflow",
                    "description": "",
                    "severity": "low|medium|high|critical",
                    "estimated_impact": "",
                    "mitigation_strategies": [],
                    "monitoring_controls": []
                }}
            ],
            "strategic_risks": [
                {{
                    "risk_type": "alignment|behavior|competitive|retention",
                    "description": "",
                    "severity": "low|medium|high|critical",
                    "business_impact": "",
                    "mitigation_strategies": [],
                    "success_metrics": []
                }}
            ],
            "risk_summary": {{
                "overall_risk_score": 0.0,
                "critical_count": 0,
                "high_count": 0,
                "recommendations": []
            }}
        }}
        """
    
    def _enhance_risk_analysis(self, parsed_result: Dict, plan_data: Dict) -> Dict[str, Any]:
        """Enhance risk analysis with additional insights"""
        enhanced = parsed_result.copy()
        
        # Calculate overall risk metrics
        enhanced["risk_metrics"] = self._calculate_risk_metrics(parsed_result)
        
        # Add industry-specific insights
        enhanced["industry_insights"] = self._get_industry_insights(plan_data)
        
        # Generate action plan
        enhanced["action_plan"] = self._generate_action_plan(parsed_result)
        
        return enhanced
    
    def _calculate_risk_metrics(self, risks: Dict) -> Dict:
        """Calculate quantitative risk metrics"""
        all_risks = []
        for category in ["compliance_risks", "operational_risks", "financial_risks", "strategic_risks"]:
            all_risks.extend(risks.get(category, []))
        
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for risk in all_risks:
            severity = risk.get("severity", "medium")
            if severity in severity_counts:
                severity_counts[severity] += 1
        
        # Risk score calculation (weighted)
        risk_score = (
            severity_counts["critical"] * 4 +
            severity_counts["high"] * 3 +
            severity_counts["medium"] * 2 +
            severity_counts["low"] * 1
        ) / max(len(all_risks), 1)
        
        return {
            "total_risks": len(all_risks),
            "severity_distribution": severity_counts,
            "weighted_risk_score": risk_score,
            "risk_level": self._get_risk_level(risk_score)
        }
    
    def _get_risk_level(self, score: float) -> str:
        """Convert numeric score to risk level"""
        if score >= 3.5:
            return "CRITICAL"
        elif score >= 2.5:
            return "HIGH"
        elif score >= 1.5:
            return "MEDIUM"
        else:
            return "LOW"
    
    def _get_required_fields(self) -> List[str]:
        return ["compliance_risks", "operational_risks", "financial_risks", "strategic_risks"]

class OracleMappingAgent(BaseAgent):
    """Specialized agent for Oracle ICM object mapping"""
    
    def __init__(self):
        super().__init__(
            name="Oracle ICM Mapper",
            description="Maps compensation requirements to Oracle ICM objects and configuration",
            model_preferences=["gpt-4", "claude-3-sonnet"]
        )
    
    async def _process(self, inputs: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        plan_structure = inputs.get("plan_structure", {})
        existing_system = context.get("existing_system", None)
        
        prompt = self._build_oracle_prompt(plan_structure, existing_system)

        from .prompting import call_llm
        result = call_llm(prompt)
        
        try:
            parsed_result = json.loads(result)
            return self._enhance_oracle_mapping(parsed_result)
        except json.JSONDecodeError:
            return self._fallback_oracle_mapping(result)
    
    def _build_oracle_prompt(self, plan_structure: Dict, existing_system: str) -> str:
        return f"""
        You are an Oracle ICM Implementation Specialist.
        
        Map the compensation plan requirements to Oracle ICM objects and configuration.
        
        Plan Requirements: {json.dumps(plan_structure, indent=2)}
        Existing System: {existing_system or "Greenfield implementation"}
        
        Provide detailed Oracle ICM mapping:
        {{
            "participants": [
                {{
                    "object_name": "Participant",
                    "attributes": [],
                    "classification_rules": [],
                    "effective_dating": {{}},
                    "data_sources": []
                }}
            ],
            "transactions": [
                {{
                    "object_name": "",
                    "source_system": "",
                    "transaction_type": "",
                    "key_attributes": [],
                    "validation_rules": [],
                    "credit_timing": "",
                    "rollback_handling": {{}}
                }}
            ],
            "credit_rules": [
                {{
                    "rule_name": "",
                    "credit_basis": "transaction|summary|event",
                    "allocation_method": "",
                    "conditions": [],
                    "effective_periods": [],
                    "dependencies": []
                }}
            ],
            "rate_tables": [
                {{
                    "table_name": "",
                    "dimensions": [],
                    "outputs": [],
                    "lookup_logic": "",
                    "versioning": {{}},
                    "validation_rules": []
                }}
            ],
            "plan_elements": [
                {{
                    "element_name": "",
                    "element_type": "commission|bonus|draw|other",
                    "calculation_frequency": "",
                    "payment_frequency": "",
                    "dependencies": [],
                    "formulas": []
                }}
            ],
            "measurements": [
                {{
                    "measurement_name": "",
                    "measurement_type": "",
                    "aggregation_method": "",
                    "performance_period": "",
                    "data_sources": []
                }}
            ],
            "roles_and_positions": [
                {{
                    "role_name": "",
                    "position_assignments": [],
                    "territory_management": {{}},
                    "hierarchy_rules": []
                }}
            ],
            "reports_and_statements": [
                {{
                    "report_name": "",
                    "report_type": "statement|analytics|management",
                    "frequency": "",
                    "recipients": [],
                    "data_elements": []
                }}
            ],
            "implementation_considerations": {{
                "complexity_assessment": "",
                "estimated_effort": "",
                "key_risks": [],
                "testing_strategy": [],
                "rollout_approach": ""
            }}
        }}
        """
    
    def _enhance_oracle_mapping(self, parsed_result: Dict) -> Dict[str, Any]:
        """Enhance Oracle mapping with implementation details"""
        enhanced = parsed_result.copy()
        
        # Add implementation roadmap
        enhanced["implementation_roadmap"] = self._generate_implementation_roadmap(parsed_result)
        
        # Add data model recommendations
        enhanced["data_model"] = self._recommend_data_model(parsed_result)
        
        # Add integration points
        enhanced["integration_points"] = self._identify_integration_points(parsed_result)
        
        return enhanced
    
    def _get_required_fields(self) -> List[str]:
        return ["participants", "transactions", "credit_rules", "plan_elements"]

class PlanningAdvisorAgent(BaseAgent):
    """Specialized agent for strategic planning recommendations"""

    def __init__(self):
        super().__init__(
            name="Planning Advisor",
            description="Provides strategic recommendations for compensation plan design",
            model_preferences=["gpt-4", "claude-3-sonnet", "gpt-3.5-turbo"],
        )

    async def _process(self, inputs: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        plan_data = inputs.get("plan_data", {})
        text = inputs.get("text", "")
        prompt = self._build_prompt(plan_data, text)

        from .prompting import call_llm
        result = call_llm(prompt)

        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {"planning_recommendations": [result.strip()]}

    def _build_prompt(self, plan_data: Dict, text: str) -> str:
        return f"""
        You are a Compensation Planning Advisor.

        Analyze the provided plan details and offer strategic recommendations to improve design and alignment with business goals.

        Plan Data: {json.dumps(plan_data, indent=2)}
        Document Text:
        <<<
        {text[:20000]}
        >>>

        Respond in JSON:
        {{
            "planning_recommendations": [
                {{"area": "", "suggestion": "", "rationale": ""}}
            ]
        }}
        """

    def _get_required_fields(self) -> List[str]:
        return ["planning_recommendations"]

class AIAgentOrchestrator:
    """Enhanced orchestrator for managing multiple AI agents"""
    
    def __init__(self):
        self.agents = {
            AgentType.DOCUMENT_ANALYZER: DocumentAnalyzerAgent(),
            AgentType.RISK_ASSESSOR: RiskAssessmentAgent(),
            AgentType.PLANNING_ADVISOR: PlanningAdvisorAgent(),
            AgentType.ORACLE_MAPPER: OracleMappingAgent(),
            # Add more agents as needed
        }
        self.execution_history = []
    
    async def analyze_with_approach(
        self, 
        text: str, 
        template: str, 
        approach: AnalysisApproach,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Execute analysis based on selected approach"""
        
        context = context or {}
        start_time = datetime.now()
        
        # Define agent workflows for each approach
        workflows = {
            AnalysisApproach.COMPREHENSIVE: [
                AgentType.DOCUMENT_ANALYZER,
                AgentType.RISK_ASSESSOR,
                AgentType.PLANNING_ADVISOR,
                AgentType.ORACLE_MAPPER
            ],
            AnalysisApproach.QUICK_SCAN: [
                AgentType.DOCUMENT_ANALYZER,
                AgentType.RISK_ASSESSOR
            ],
            AnalysisApproach.RISK_FOCUSED: [
                AgentType.DOCUMENT_ANALYZER,
                AgentType.RISK_ASSESSOR
            ],
            AnalysisApproach.TECHNICAL_MAPPING: [
                AgentType.DOCUMENT_ANALYZER,
                AgentType.ORACLE_MAPPER
            ]
        }
        
        selected_agents = workflows.get(approach, workflows[AnalysisApproach.COMPREHENSIVE])
        
        results = {
            "approach": approach.value,
            "execution_metadata": {
                "start_time": start_time.isoformat(),
                "agents_used": [agent.value for agent in selected_agents]
            },
            "agent_results": {}
        }
        
        # Execute agents in sequence
        current_context = context.copy()
        
        for agent_type in selected_agents:
            agent = self.agents[agent_type]
            
            # Prepare inputs based on previous results
            inputs = self._prepare_agent_inputs(agent_type, text, template, results)
            
            # Execute agent
            agent_result = await agent.execute(inputs, current_context)
            
            # Store result
            results["agent_results"][agent_type.value] = {
                "status": agent_result.status,
                "execution_time": agent_result.execution_time,
                "confidence_score": agent_result.confidence_score,
                "data": agent_result.data,
                "errors": agent_result.errors or [],
                "warnings": agent_result.warnings or []
            }
            
            # Update context for next agent
            if agent_result.status == "success":
                current_context.update(agent_result.data)
        
        # Calculate overall metrics
        total_time = (datetime.now() - start_time).total_seconds()
        results["execution_metadata"].update({
            "end_time": datetime.now().isoformat(),
            "total_execution_time": total_time,
            "overall_confidence": self._calculate_overall_confidence(results),
            "success_rate": self._calculate_success_rate(results)
        })
        
        # Generate consolidated insights
        results["consolidated_insights"] = await self._generate_insights(results)
        
        return results
    
    def _prepare_agent_inputs(
        self, 
        agent_type: AgentType, 
        text: str, 
        template: str, 
        previous_results: Dict
    ) -> Dict[str, Any]:
        """Prepare inputs for each agent based on previous results"""
        
        base_inputs = {"text": text, "template": template}
        
        if agent_type == AgentType.DOCUMENT_ANALYZER:
            return base_inputs
        
        elif agent_type == AgentType.RISK_ASSESSOR:
            doc_result = previous_results.get("agent_results", {}).get("document_analyzer", {})
            return {
                "plan_data": doc_result.get("data", {}),
                "template": template
            }
        
        elif agent_type == AgentType.ORACLE_MAPPER:
            doc_result = previous_results.get("agent_results", {}).get("document_analyzer", {})
            return {
                "plan_structure": doc_result.get("data", {}),
                "template": template
            }

        elif agent_type == AgentType.PLANNING_ADVISOR:
            doc_result = previous_results.get("agent_results", {}).get("document_analyzer", {})
            return {
                "plan_data": doc_result.get("data", {}),
                "text": text,
                "template": template
            }

        return base_inputs
    
    def _calculate_overall_confidence(self, results: Dict) -> float:
        """Calculate overall confidence score across all agents"""
        agent_results = results.get("agent_results", {})
        
        if not agent_results:
            return 0.0
        
        confidence_scores = [
            result.get("confidence_score", 0.0) 
            for result in agent_results.values()
            if result.get("status") == "success"
        ]
        
        return sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
    
    def _calculate_success_rate(self, results: Dict) -> float:
        """Calculate success rate across all agents"""
        agent_results = results.get("agent_results", {})
        
        if not agent_results:
            return 0.0
        
        successful = sum(1 for result in agent_results.values() if result.get("status") == "success")
        total = len(agent_results)
        
        return successful / total
    
    async def _generate_insights(self, results: Dict) -> Dict[str, Any]:
        """Generate consolidated insights from all agent results"""
        
        insights = {
            "key_findings": [],
            "critical_issues": [],
            "recommendations": [],
            "next_steps": []
        }
        
        # Extract insights from each agent
        agent_results = results.get("agent_results", {})
        
        # Document analyzer insights
        if "document_analyzer" in agent_results:
            doc_data = agent_results["document_analyzer"].get("data", {})
            if doc_data.get("key_metrics"):
                insights["key_findings"].append("Identified key performance metrics and calculation methods")
        
        # Risk assessor insights  
        if "risk_assessor" in agent_results:
            risk_data = agent_results["risk_assessor"].get("data", {})
            risk_metrics = risk_data.get("risk_metrics", {})
            
            if risk_metrics.get("risk_level") in ["HIGH", "CRITICAL"]:
                insights["critical_issues"].append(f"High risk level detected: {risk_metrics.get('risk_level')}")
        
        # Oracle mapper insights
        if "oracle_mapper" in agent_results:
            oracle_data = agent_results["oracle_mapper"].get("data", {})
            implementation = oracle_data.get("implementation_considerations", {})

            if implementation.get("complexity_assessment"):
                insights["recommendations"].append("Oracle ICM implementation roadmap generated")

        # Planning advisor insights
        if "planning_advisor" in agent_results:
            plan_data = agent_results["planning_advisor"].get("data", {})
            if plan_data.get("planning_recommendations"):
                insights["recommendations"].append("Strategic planning recommendations provided")

        return insights

# Export main classes
__all__ = [
    "AIAgentOrchestrator",
    "AnalysisApproach",
    "AgentType",
    "DocumentAnalyzerAgent",
    "RiskAssessmentAgent",
    "OracleMappingAgent",
    "PlanningAdvisorAgent",
]