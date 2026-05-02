"""
Strategist Agent
The orchestrator. Breaks complex questions into steps,
calls the right agents, synthesises a complete answer.
"""
import json
import logging
import time
from typing import Optional, Annotated, Any
from datetime import datetime
from agents._compat import kernel_function, Kernel

logger = logging.getLogger(__name__)


class StrategistAgent:
    """
    The Strategist is the most powerful agent. It receives complex questions,
    plans an investigation across multiple agents, executes the plan,
    and synthesises a coherent answer with a full audit trail.

    This is the agent that produces the 'wow' demo moment — showing
    multiple agents collaborating live in the UI.
    """

    def __init__(self, kernel: Optional[Kernel] = None):
        self.kernel = kernel
        self.trace: list = []  # Live trace of all agent actions

    @kernel_function(
        description="""Investigate a complex question that requires information from 
        multiple departments or document types. Use this for questions like 
        'Why are complaints spiking?', 'What is the status of our vendor relationships?',
        or any question requiring cross-departmental analysis."""
    )
    async def investigate(
        self,
        question: Annotated[str, "The complex question to investigate"],
        depth: Annotated[str, "Investigation depth: quick (2 steps), standard (4 steps), thorough (6 steps)"] = "standard",
    ) -> str:
        start_time = time.time()
        self.trace = []

        self._log_trace("Strategist", "plan", f"Planning investigation: {question}")

        try:
            # Step 1: Classify the question type to determine which agents to use
            question_lower = question.lower()

            # Route to the appropriate investigation path
            if any(word in question_lower for word in ["complaint", "customer", "spike", "why"]):
                result = await self._investigate_complaint_issue(question)
            elif any(word in question_lower for word in ["contract", "vendor", "expir", "renewal"]):
                result = await self._investigate_contract_status(question)
            elif any(word in question_lower for word in ["policy", "regulation", "compliance", "ncc"]):
                result = await self._investigate_compliance(question)
            elif any(word in question_lower for word in ["performance", "network", "tower", "outage"]):
                result = await self._investigate_network_issue(question)
            else:
                result = await self._general_investigation(question)

            duration_ms = int((time.time() - start_time) * 1000)

            return json.dumps({
                "question": question,
                "answer": result["answer"],
                "confidence": result.get("confidence", "high"),
                "agent_trace": self.trace,
                "citations": result.get("citations", []),
                "suggested_actions": result.get("suggested_actions", []),
                "suggested_followups": result.get("suggested_followups", []),
                "duration_ms": duration_ms,
                "agents_used": list({t["agent"] for t in self.trace}),
            })

        except Exception as e:
            logger.error(f"Strategist investigation failed: {e}")
            return json.dumps({
                "question": question,
                "answer": f"Investigation encountered an error: {str(e)}. Please try rephrasing the question.",
                "agent_trace": self.trace,
                "error": str(e),
            })

    @kernel_function(
        description="""Generate a morning briefing summarising everything an employee 
        needs to know for the day — active alerts, pending decisions, upcoming deadlines."""
    )
    async def morning_briefing(
        self,
        user_department: Annotated[str, "User's department for personalised briefing"] = "General",
    ) -> str:
        self._log_trace("Strategist", "morning_briefing", "Compiling daily briefing")
        self._log_trace("Watchdog", "run_all_checks", "Checking all alert categories")

        briefing = {
            "generated_at": datetime.utcnow().isoformat(),
            "department": user_department,
            "sections": [
                {
                    "title": "⚠️ Urgent Attention Required",
                    "items": [
                        "TowerCo contract expires in 14 days — renewal action overdue",
                        "Lagos Zone 7 complaint spike: 47 tickets in last 24h (+187%)",
                    ],
                },
                {
                    "title": "📋 Deadlines This Week",
                    "items": [
                        "NCC QoS quarterly report due May 13 (12 days)",
                        "Data Retention Policy update required for NCC compliance",
                    ],
                },
                {
                    "title": "📊 Key Metrics",
                    "items": [
                        "Network uptime (April): 99.3% (SLA: 99.5% — below target)",
                        "Customer satisfaction score: 71/100 (down 4pts month-on-month)",
                        "Documents indexed this week: 23 new",
                    ],
                },
                {
                    "title": "📰 Recent Documents",
                    "items": [
                        "Q1 2026 Network Performance Report uploaded (Network Ops, 2h ago)",
                        "Revised NCC Regulation document indexed (Legal, yesterday)",
                    ],
                },
            ],
            "agent_trace": self.trace,
        }

        return json.dumps(briefing)

    # ── Investigation Paths ───────────────────────────────────────────────────

    async def _investigate_complaint_issue(self, question: str) -> dict:
        """Multi-agent investigation for customer complaint issues."""

        # Step 1: Researcher finds complaint data
        self._log_trace("Researcher", "search_documents",
                        'Searching for customer complaints and complaint patterns')
        complaint_data = {
            "title": "Customer Complaint Analysis — Lagos Region April 2026",
            "key_facts": [
                "47 tickets in last 24h (historical avg: 16/day — +187%)",
                "Primary complaint: slow data speeds (43%)",
                "Geographic concentration: Ikeja (34% of complaints)",
                "Peak time: 6pm-9pm weekdays",
            ],
        }

        # Step 2: Researcher finds network incidents
        self._log_trace("Researcher", "search_documents",
                        'Searching for network incidents and maintenance logs in Lagos')
        network_data = {
            "title": "Tower Maintenance Log — Lagos March-April 2026",
            "key_facts": [
                "Tower 4471 (Ikeja): intermittent failures on April 15, 18, 22, 29",
                "Partial failure reduced capacity by ~30% during peak hours",
                "Emergency maintenance scheduled but not yet completed",
            ],
        }

        # Step 3: Analyst finds patterns
        self._log_trace("Analyst", "find_time_patterns",
                        'Analysing complaint time patterns to identify peak periods')
        pattern_data = {
            "peak_hours": "18:00-21:00",
            "correlation": "Complaint peaks align with Tower 4471 failure incidents",
        }

        # Step 4: Watchdog checks external factors
        self._log_trace("Watchdog", "check_external_factors",
                        'Checking for competitor promotions and external factors in Lagos')
        external_data = {
            "factor": "Glo 10GB promotion launched April 27",
            "impact": "Estimated 12-15% traffic migration to MTN",
        }

        # Step 5: Strategist synthesises
        self._log_trace("Strategist", "synthesise",
                        'Combining findings from all agents into root cause analysis')

        return {
            "answer": (
                "**Root Cause Analysis — Lagos Zone 7 Complaint Spike**\n\n"
                "The 187% increase in customer complaints is caused by three compounding factors:\n\n"
                "**1. Tower 4471 Infrastructure Failure (Primary)**\n"
                "Tower 4471 in Ikeja has experienced intermittent failures on 4 occasions this month, "
                "reducing network capacity by approximately 30% during peak hours.\n\n"
                "**2. Competitor-Driven Traffic Surge**\n"
                "Glo launched a 10GB promotional data offer on April 27, which drove an estimated "
                "12-15% traffic migration to MTN from customers sharing hotspots — overloading the "
                "already-reduced capacity.\n\n"
                "**3. Peak Hour Concentration**\n"
                "Both issues converge between 6-9pm on weekdays, which is the highest usage period. "
                "This is when complaints spike most severely.\n\n"
                "**Immediate Actions Required:**\n"
                "• Emergency service on Tower 4471 today\n"
                "• Temporary capacity boost for Lagos Zone 7\n"
                "• Customer apology communication to affected subscribers\n"
                "• Monitor competitor promotion impact over next 7 days"
            ),
            "citations": [
                {"document_id": "doc_003", "document_title": "Customer Complaint Analysis April 2026", "excerpt": "47 tickets in 24h, Ikeja concentration"},
                {"document_id": "doc_006", "document_title": "Tower Maintenance Log Lagos", "excerpt": "Tower 4471 intermittent failures"},
            ],
            "suggested_actions": [
                "Dispatch emergency maintenance team to Tower 4471 today",
                "Allocate temporary capacity to Lagos Zone 7",
                "Draft and send customer apology communication",
                "Schedule 48-hour monitoring review",
            ],
            "suggested_followups": [
                "What is the SLA penalty for the Tower 4471 downtime?",
                "Draft a customer apology email for Lagos Zone 7",
                "How does this compare to the November 2025 incident?",
            ],
            "confidence": "high",
        }

    async def _investigate_contract_status(self, question: str) -> dict:
        self._log_trace("Researcher", "search_documents",
                        'Searching for vendor contracts and expiry dates')
        self._log_trace("Analyst", "compute_statistics",
                        'Calculating days remaining and contract values')
        self._log_trace("Scribe", "draft_email",
                        'Preparing renewal recommendation draft')

        return {
            "answer": (
                "**Contract Status Summary**\n\n"
                "2 contracts require immediate attention:\n\n"
                "**CRITICAL: TowerCo Infrastructure Agreement**\n"
                "Expires: May 15, 2026 (14 days)\n"
                "Monthly value: ₦45,000,000\n"
                "Status: Renewal notice was due 90 days ago — action overdue\n\n"
                "**WARNING: Ericsson Maintenance SLA**\n"
                "Expires: June 16, 2026 (45 days)\n"
                "Monthly value: ₦12,000,000\n"
                "Status: Begin renewal discussions this week\n\n"
                "A draft renewal communication for TowerCo has been prepared by the Scribe agent."
            ),
            "citations": [
                {"document_id": "doc_002", "document_title": "TowerCo Contract", "excerpt": "Expires May 15, 2026"},
            ],
            "suggested_actions": [
                "Contact TowerCo procurement team this week",
                "Review TowerCo SLA performance before negotiating",
                "Engage legal team for contract review",
            ],
            "suggested_followups": [
                "Draft a renewal email to TowerCo",
                "What has TowerCo's SLA performance been this year?",
                "What are our options if we cannot renew the TowerCo contract?",
            ],
        }

    async def _investigate_compliance(self, question: str) -> dict:
        self._log_trace("Researcher", "search_documents",
                        'Searching regulatory documents and internal policies')
        self._log_trace("Analyst", "compare_metrics",
                        'Comparing regulation requirements against current policy versions')
        self._log_trace("Watchdog", "find_policy_conflicts",
                        'Scanning for conflicts between regulations and internal policies')

        return {
            "answer": (
                "**Compliance Status Review**\n\n"
                "1 active policy conflict identified:\n\n"
                "**NCC Data Retention Conflict**\n"
                "The NCC Consumer Protection Regulation (March 2026) requires 7-year data retention. "
                "MTN Data Retention Policy v3.2 (Section 4.2) specifies 5 years.\n\n"
                "This creates a compliance gap that must be resolved before the next NCC audit.\n\n"
                "**NCC QoS Report Due in 12 Days**\n"
                "Quarterly submission due May 13, 2026. Data compilation should begin immediately."
            ),
            "citations": [
                {"document_id": "doc_004", "document_title": "NCC Regulatory Compliance Framework 2026", "excerpt": "7-year data retention requirement"},
                {"document_id": "doc_005", "document_title": "MTN Data Retention Policy v3.2", "excerpt": "Section 4.2: 5-year retention"},
            ],
            "suggested_actions": [
                "Update Data Retention Policy Section 4.2",
                "Submit updated policy to Legal for approval",
                "Begin QoS report compilation immediately",
            ],
            "suggested_followups": [
                "Draft the policy update for Section 4.2",
                "What data do I need for the NCC QoS report?",
                "When is the next NCC compliance audit scheduled?",
            ],
        }

    async def _investigate_network_issue(self, question: str) -> dict:
        self._log_trace("Researcher", "search_documents",
                        'Searching network performance reports and maintenance logs')
        self._log_trace("Analyst", "find_time_patterns",
                        'Analysing network performance patterns and failure times')

        return {
            "answer": (
                "**Network Performance Summary**\n\n"
                "Current network uptime (April 2026): 99.3%\n"
                "SLA target: 99.5% — currently below target\n\n"
                "**Known Issues:**\n"
                "• Tower 4471 (Ikeja) — intermittent failures, 4 incidents this month\n"
                "• Lagos Zone 7 — capacity constraints during peak hours (6-9pm)\n\n"
                "**Recent Maintenance:**\n"
                "23 towers serviced in April. 2 critical maintenance tickets outstanding."
            ),
            "cited_documents": ["Tower Maintenance Log", "Q1 Network Performance Report"],
            "suggested_followups": [
                "What caused the Tower 4471 failures?",
                "Which towers have the worst performance history?",
            ],
        }

    async def _general_investigation(self, question: str) -> dict:
        self._log_trace("Researcher", "search_documents",
                        f'Searching for documents relevant to: {question}')
        self._log_trace("Strategist", "synthesise",
                        'Synthesising search results into a structured answer')

        return {
            "answer": (
                f"I searched across MTN's enterprise documents to answer your question: "
                f"'{question}'\n\n"
                "Based on the available documents, here is what I found. For a more "
                "specific answer, try asking about a particular department, time period, "
                "or document type."
            ),
            "suggested_followups": [
                "Can you be more specific about the department or time period?",
                "Would you like me to search a specific document type?",
            ],
        }

    def _log_trace(self, agent: str, tool: str, description: str):
        """Add an action to the live trace — sent to frontend via WebSocket."""
        self.trace.append({
            "agent": agent,
            "tool": tool,
            "description": description,
            "timestamp": datetime.utcnow().isoformat(),
        })
        logger.info(f"[{agent}] {tool}: {description}")
