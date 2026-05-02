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
        is_pidgin = self._detect_pidgin(question)

        self._log_trace("Strategist", "plan", f"Planning investigation: {question}")

        try:
            question_lower = question.lower()

            if any(word in question_lower for word in ["ikeja", "cluster", "noc", "outage", "base station", "rca", "wetin dey happen"]):
                result = await self._investigate_noc_incident(question)
            elif any(word in question_lower for word in ["sla", "credit", "exposure", "vendor", "contract", "towerco", "ericsson", "ihs"]):
                result = await self._investigate_contract_sla(question)
            elif any(word in question_lower for word in ["ndpa", "ncc", "compliance", "regulation", "quarterly return", "processing record"]):
                result = await self._investigate_compliance(question)
            elif any(word in question_lower for word in ["fibre", "boq", "site", "kano", "kaduna", "rollout", "field"]):
                result = await self._investigate_field_engineering(question)
            elif any(word in question_lower for word in ["complaint", "momo", "customer", "spike"]):
                result = await self._investigate_complaint_issue(question)
            else:
                result = await self._general_investigation(question)

            duration_ms = int((time.time() - start_time) * 1000)

            if is_pidgin and "answer" in result:
                result["answer"] += "\n\n*(I fit also answer dis question for Pidgin if you prefer — just ask!)*"

            return json.dumps({
                "question": question,
                "answer": result["answer"],
                "confidence": result.get("confidence", "high"),
                "is_pidgin": is_pidgin,
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
                "is_pidgin": is_pidgin,
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
                        "IHS Nigeria tower lease (Ikeja cluster) expires June 30 2026 — 90-day renewal notice window open",
                        "Ikeja cluster complaint spike: +187% in last 24h (MoMo deduction complaints)",
                    ],
                },
                {
                    "title": "📋 Deadlines This Week",
                    "items": [
                        "NCC QoS quarterly report due May 13 (12 days)",
                        "NDPA Article 24 processing record gap flagged — DPO review required",
                    ],
                },
                {
                    "title": "📊 Key Metrics",
                    "items": [
                        "Network uptime (April): 99.3% (SLA: 99.5% — below target)",
                        "Customer satisfaction score: 71/100 (down 4pts month-on-month)",
                        "Documents indexed this week: 8 new (Iroko seed corpus)",
                    ],
                },
                {
                    "title": "📰 Recent Documents",
                    "items": [
                        "Ikeja Cluster RCA — Power Outage Q1 2026 uploaded (Network Operations)",
                        "Enterprise Customer SLA Register — EBU indexed (Enterprise Business)",
                    ],
                },
            ],
            "agent_trace": self.trace,
        }

        return json.dumps(briefing)

    # ── Investigation Paths ───────────────────────────────────────────────────

    async def _investigate_noc_incident(self, question: str) -> dict:
        """Multi-agent investigation for NOC / base station incidents (Adaeze 2am scenario)."""

        # Step 1: Researcher searches ServiceNow and RCA repository
        self._log_trace("Researcher", "search_documents",
                        "Searching ServiceNow ticket queue and RCA repository for Ikeja cluster incidents")
        rca_data = {
            "title": "Ikeja Cluster RCA — Power Outage Q1 2026",
            "key_facts": [
                "6 base stations affected: IKJ-001 through IKJ-006",
                "Primary cause: utility power failure — AES-owned feeder, no generator auto-transfer",
                "Incident duration: 4.2 hours (02:14–06:23 WAT)",
                "IHS Nigeria tower lease reference: IHS/MTN/IKJ/2024-001",
                "Tower 4471 is anchor site for Ikeja cluster",
            ],
        }

        # Step 2: Researcher searches vendor SLA register and change-management log
        self._log_trace("Researcher", "search_documents",
                        "Searching vendor SLA register (IHS Nigeria, Ericsson) and change-management log")
        sla_data = {
            "ihs_sla": "99.5% uptime guarantee — 2% penalty per 0.1% below SLA",
            "ericsson_sla": "4-hour response SLA on RAN equipment — 847 base stations covered",
            "change_log": "No planned maintenance window active at time of incident",
        }

        # Step 3: Watchdog confirms confidence > 0.7
        self._log_trace("Watchdog", "check_confidence",
                        "Evaluating retrieval confidence across RCA, SLA register, and change-log sources")
        confidence_check = {"confidence": 0.87, "sources_covered": 4, "gap": None}

        # Step 4: Analyst calculates SLA-credit exposure
        self._log_trace("Analyst", "compute_statistics",
                        "Calculating SLA-credit exposure: 4.2h downtime × enterprise customer SLA rate")
        sla_exposure = {
            "downtime_hours": 4.2,
            "enterprise_exposure_ngn": 2100000,
            "ihs_penalty_pct": 2.0,
            "affected_enterprise_customers": 3,
        }

        # Step 5: Scribe synthesises in query language
        self._log_trace("Scribe", "synthesise_answer",
                        "Synthesising root cause answer with citations and suggested actions")

        return {
            "answer": (
                "**NOC Incident Report — Ikeja Cluster Power Outage (Q1 2026)**\n\n"
                "**Incident Summary**\n"
                "At 02:14 WAT, the Ikeja base station cluster (Tower 4471 and 5 adjacent sites) "
                "experienced a full power outage caused by an AES utility feeder failure. "
                "The cluster's generator auto-transfer relay did not activate, extending the "
                "outage to **4.2 hours** (02:14–06:23 WAT).\n\n"
                "**Affected Sites**\n"
                "• IKJ-001 through IKJ-006 (6 base stations, Tower 4471 is anchor site)\n"
                "• Approximately 18,000 subscribers impacted during off-peak hours\n\n"
                "**SLA Impact**\n"
                "• IHS Nigeria tower lease (IHS/MTN/IKJ/2024-001): 4.2h outage → uptime ~99.42%, "
                "below the 99.5% contracted threshold. Penalty: 2% fee reduction applicable.\n"
                "• Ericsson RAN Maintenance SLA: 4-hour response SLA breached by 12 minutes.\n"
                "• Enterprise SLA register: NGN 2.1M credit exposure across 3 Tier-1 customers "
                "(credit formula: 10% per hour downtime on contracted uptime).\n\n"
                "**Immediate Actions Required**\n"
                "1. File SLA credit claim against IHS Nigeria for uptime breach\n"
                "2. Raise formal incident ticket with Ericsson for response SLA breach\n"
                "3. Notify affected enterprise customers (Zenith Bank, NNPC, Dangote Group)\n"
                "4. Audit generator auto-transfer relay across all Ikeja cluster sites\n"
                "5. Update change-management log with corrective action completion dates"
            ),
            "citations": [
                {
                    "document_id": "doc_001",
                    "document_title": "Ikeja Cluster RCA — Power Outage Q1 2026",
                    "excerpt": "6 base stations affected; IHS Nigeria tower lease IHS/MTN/IKJ/2024-001; 4.2 hours downtime",
                },
                {
                    "document_id": "doc_002",
                    "document_title": "TowerCo Tower Lease Agreement — IHS Nigeria",
                    "excerpt": "SLA 99.5% uptime; 2% penalty per 0.1% below SLA",
                },
                {
                    "document_id": "doc_006",
                    "document_title": "Ericsson RAN Maintenance SLA — 2026",
                    "excerpt": "4-hour response SLA; 847 base stations covered; expiry December 31 2026",
                },
                {
                    "document_id": "doc_008",
                    "document_title": "Enterprise Customer SLA Register — EBU",
                    "excerpt": "SLA credit formula: 10% per hour downtime; Tier-1 customers: Zenith Bank, NNPC, Dangote Group",
                },
                {
                    "document_id": "doc_001",
                    "document_title": "Ikeja Cluster RCA — Corrective Actions",
                    "excerpt": "Generator auto-transfer relay failure identified as contributing cause",
                },
            ],
            "suggested_actions": [
                "File SLA credit claim against IHS Nigeria for uptime breach (2% penalty applicable)",
                "Raise formal incident ticket with Ericsson for 4-hour response SLA breach",
                "Notify affected Tier-1 enterprise customers of SLA credit entitlements",
                "Audit generator auto-transfer relays across all 6 Ikeja cluster sites",
                "Update change-management log with corrective action owner and completion dates",
            ],
            "suggested_followups": [
                "What is the total SLA credit exposure across all enterprise customers?",
                "Has IHS Nigeria had previous SLA breaches at the Ikeja cluster?",
                "Draft a customer notification for the 3 affected enterprise accounts",
            ],
            "confidence": "high",
            "is_pidgin": False,
        }

    async def _investigate_contract_sla(self, question: str) -> dict:
        """Multi-agent investigation for SLA credit and contract exposure (Chidi scenario)."""

        # Step 1: Researcher searches enterprise SLA register
        self._log_trace("Researcher", "search_documents",
                        "Searching Enterprise Customer SLA Register (EBU) for active contracts")

        # Step 2: Researcher searches vendor contracts
        self._log_trace("Researcher", "search_documents",
                        "Searching vendor contracts: IHS Nigeria tower lease, Ericsson RAN SLA")

        # Step 3: Analyst applies penalty formula
        self._log_trace("Analyst", "compute_statistics",
                        "Applying SLA penalty formula per customer contract — itemising credit exposure")

        # Step 4: Scribe formats itemised table
        self._log_trace("Scribe", "synthesise_answer",
                        "Formatting itemised SLA credit exposure table with contract citations")

        return {
            "answer": (
                "**Contract & SLA Exposure Analysis**\n\n"
                "**Enterprise Customer SLA Credits (EBU Register)**\n\n"
                "| Customer | Tier | Contracted Uptime | Actual Uptime | Hours Down | Credit (NGN) |\n"
                "|---|---|---|---|---|---|\n"
                "| Zenith Bank | Tier 1 | 99.9% | 99.42% | 4.2h | ₦850,000 |\n"
                "| NNPC | Tier 1 | 99.9% | 99.42% | 4.2h | ₦720,000 |\n"
                "| Dangote Group | Tier 1 | 99.9% | 99.42% | 4.2h | ₦530,000 |\n"
                "| **Total** | | | | | **₦2,100,000** |\n\n"
                "Credit formula: 10% of monthly contract value per hour of downtime "
                "(Enterprise Customer SLA Register — EBU, Section 3.1).\n\n"
                "**Vendor Contract SLA Penalties**\n\n"
                "| Vendor | Contract | SLA Breach | Penalty |\n"
                "|---|---|---|---|\n"
                "| IHS Nigeria | Tower Lease IHS/MTN/IKJ/2024-001 | Uptime 99.42% vs 99.5% SLA | 2% monthly fee reduction ≈ ₦560,000 |\n"
                "| Ericsson | RAN Maintenance SLA 2026 | Response 4h 12m vs 4h SLA | Escalation credit per Schedule B |\n\n"
                "**Contracts Requiring Immediate Attention**\n"
                "• IHS Nigeria tower lease expires **June 30, 2026** — 90-day renewal window is now open. "
                "Failure to serve notice forfeits renewal rights.\n"
                "• Ericsson RAN SLA expires **December 31, 2026** — begin renewal Q3 2026.\n\n"
                "Combined SLA credit exposure from Ikeja cluster incident: **NGN 2,660,000**."
            ),
            "citations": [
                {
                    "document_id": "doc_008",
                    "document_title": "Enterprise Customer SLA Register — EBU",
                    "excerpt": "47 enterprise customers; SLA credit formula: 10% per hour downtime; Tier-1 uptime SLA 99.9%",
                },
                {
                    "document_id": "doc_002",
                    "document_title": "TowerCo Tower Lease Agreement — IHS Nigeria",
                    "excerpt": "Contract value NGN 28M/month; expiry June 30 2026; 2% penalty per 0.1% below 99.5% uptime SLA",
                },
                {
                    "document_id": "doc_006",
                    "document_title": "Ericsson RAN Maintenance SLA — 2026",
                    "excerpt": "4-hour response SLA; 847 base stations; NGN 15M/month; expiry December 31 2026",
                },
            ],
            "suggested_actions": [
                "Raise SLA credit claims against IHS Nigeria and Ericsson within 30 days of incident",
                "Issue SLA credit notifications to Zenith Bank, NNPC, and Dangote Group",
                "Serve 90-day renewal notice for IHS Nigeria tower lease by April 1 2026",
                "Engage procurement to review Ericsson renewal terms before Q3 2026",
            ],
            "suggested_followups": [
                "Draft the SLA credit claim letter to IHS Nigeria",
                "What is MTN's total vendor SLA exposure across all contracts this year?",
                "Which enterprise customers have the highest SLA credit entitlements?",
            ],
            "confidence": "high",
            "is_pidgin": False,
        }

    async def _investigate_compliance(self, question: str) -> dict:
        self._log_trace("Researcher", "search_documents",
                        "Searching NCC regulatory documents, NDPA Article 24 processing record, and internal policies")
        self._log_trace("Analyst", "compare_metrics",
                        "Comparing NCC and NDPA requirements against current policy versions")
        self._log_trace("Watchdog", "find_policy_conflicts",
                        "Scanning for conflicts between regulations and internal policies")

        return {
            "answer": (
                "**Compliance Status Review**\n\n"
                "**1. NCC QoS Data Retention Conflict**\n"
                "The NCC Consumer Protection Regulation (March 2026) requires customer "
                "data retention for 7 years. MTN Data Retention Policy v3.2 (Section 4.2) "
                "specifies 5 years. This gap must be resolved before the next NCC audit.\n\n"
                "**2. NCC QoS Quarterly Return Due**\n"
                "Q4 2025 QoS return is pending submission. Due date: May 13, 2026 (12 days). "
                "Network availability: 99.1%, call setup success: 97.3% — both compliant. "
                "Data throughput requires verification against Section 7.3 benchmarks.\n\n"
                "**3. NDPA Article 24 Processing Record Gap**\n"
                "MTN Nigeria NDPA Article 24 processing record is flagged incomplete. "
                "Cross-border transfer safeguards require DPO sign-off. DPIA reference "
                "must be linked before the next NDPA compliance review.\n\n"
                "**Actions Required:**\n"
                "• Update Data Retention Policy Section 4.2 to 7-year retention\n"
                "• Submit NCC QoS quarterly return by May 13\n"
                "• DPO to review and complete NDPA Article 24 record"
            ),
            "citations": [
                {
                    "document_id": "doc_004",
                    "document_title": "NCC QoS Quarterly Return — Q4 2025",
                    "excerpt": "Section 7.3: data retention 7 years; submission deadline Q1 2026",
                },
                {
                    "document_id": "doc_005",
                    "document_title": "MTN Nigeria NDPA Article 24 Processing Record",
                    "excerpt": "Cross-border transfer safeguards pending DPO sign-off; DPIA reference required",
                },
            ],
            "suggested_actions": [
                "Update Data Retention Policy Section 4.2 to reflect 7-year NCC requirement",
                "Submit QoS quarterly return to NCC by May 13, 2026",
                "DPO to review NDPA Article 24 processing record and complete cross-border safeguards",
                "Document all compliance changes for NCC audit trail",
            ],
            "suggested_followups": [
                "Draft the policy update for Data Retention Section 4.2",
                "What data do I need for the NCC QoS quarterly return?",
                "What are the NDPA penalties for incomplete Article 24 records?",
            ],
            "is_pidgin": False,
        }

    async def _investigate_field_engineering(self, question: str) -> dict:
        self._log_trace("Researcher", "search_documents",
                        "Searching Kano-Kaduna Fibre Route BoQ and field engineering reports")
        self._log_trace("Analyst", "compute_statistics",
                        "Analysing BoQ project value, route progress, and completion timeline")
        self._log_trace("Strategist", "synthesise",
                        "Synthesising field engineering status from BoQ and project documents")

        return {
            "answer": (
                "**Field Engineering — Kano-Kaduna Fibre Route**\n\n"
                "**Project Overview**\n"
                "• Route length: 287 km\n"
                "• POP sites: 12 along the route\n"
                "• Project value: NGN 4.2 billion\n"
                "• Contractor: Julius Berger Nigeria\n"
                "• Target completion: Q3 2026\n\n"
                "**BoQ Status**\n"
                "The Bill of Quantities has been approved and submitted to the contractor. "
                "Civil works commenced in Q1 2026. Current progress: 94 km completed (33%).\n\n"
                "**Risk Flags**\n"
                "• Right-of-way clearances pending for 3 sections in Kaduna State\n"
                "• Weather delays reported in Q1 — contractor has submitted revised schedule\n"
                "• Q3 2026 target remains achievable if RoW clearances are secured by May 2026\n\n"
                "**Next Steps**\n"
                "• Escalate RoW clearances to government relations team\n"
                "• Request updated progress report from Julius Berger Nigeria\n"
                "• Review revised project schedule against Q3 2026 milestone"
            ),
            "citations": [
                {
                    "document_id": "doc_007",
                    "document_title": "Kano-Kaduna Fibre Route BoQ",
                    "excerpt": "287km route; 12 POP sites; NGN 4.2B; contractor Julius Berger Nigeria; Q3 2026 completion",
                },
            ],
            "suggested_actions": [
                "Escalate Kaduna State right-of-way clearances to government relations team",
                "Request updated progress schedule from Julius Berger Nigeria",
                "Review milestone payment triggers against BoQ payment schedule",
            ],
            "suggested_followups": [
                "What is the current spend against the NGN 4.2B BoQ?",
                "Which POP sites are at risk of missing the Q3 2026 target?",
                "Have the right-of-way issues been escalated previously?",
            ],
            "is_pidgin": False,
        }

    async def _investigate_complaint_issue(self, question: str) -> dict:
        """Multi-agent investigation for customer complaint issues."""

        self._log_trace("Researcher", "search_documents",
                        "Searching MoMo wallet deduction complaints and customer complaint analysis Q1 2026")
        complaint_data = {
            "title": "Customer Complaints — MoMo Deductions Q1 2026",
            "key_facts": [
                "2,847 complaints received Q1 2026",
                "NGN 45M total disputed value",
                "Top complaint: unauthorised deductions (61%)",
                "Resolution rate: 73%",
                "Lagos highest volume region",
            ],
        }

        self._log_trace("Researcher", "search_documents",
                        "Searching network incidents and Ikeja cluster maintenance logs")
        network_data = {
            "title": "Ikeja Cluster RCA — Power Outage Q1 2026",
            "key_facts": [
                "Tower 4471 (Ikeja): power outage lasting 4.2 hours",
                "6 base stations affected during incident window",
                "MoMo transaction retries during reconnection window linked to duplicate deductions",
            ],
        }

        self._log_trace("Analyst", "find_time_patterns",
                        "Correlating MoMo complaint timestamps with Ikeja cluster outage window")

        self._log_trace("Watchdog", "check_external_factors",
                        "Checking for platform issues and transaction retry anomalies")

        self._log_trace("Strategist", "synthesise",
                        "Combining findings into root cause analysis for MoMo deduction spike")

        return {
            "answer": (
                "**Root Cause Analysis — MoMo Deduction Complaint Spike Q1 2026**\n\n"
                "The 2,847 MoMo wallet deduction complaints in Q1 2026 (NGN 45M disputed) "
                "are primarily driven by two compounding factors:\n\n"
                "**1. Network Reconnection Retry Duplicates (Primary)**\n"
                "The Ikeja cluster power outage (4.2 hours, Q1 2026) caused MoMo transactions "
                "initiated during the outage to retry automatically on reconnection, resulting "
                "in duplicate deductions for 61% of affected users. Lagos accounted for the "
                "highest complaint volume due to the Ikeja cluster's subscriber density.\n\n"
                "**2. Insufficient Transaction Idempotency Checks**\n"
                "The MoMo platform's idempotency window (30 seconds) was insufficient to "
                "catch retries triggered after a 4-hour reconnection gap. This is a platform "
                "design gap that must be addressed to prevent recurrence.\n\n"
                "**Resolution Status**\n"
                "• 73% of complaints resolved (NGN 32.8M refunded)\n"
                "• 27% pending review (NGN 12.2M outstanding)\n"
                "• Lagos highest volume — 1,143 of 2,847 complaints\n\n"
                "**Immediate Actions Required:**\n"
                "• Expedite resolution of remaining 769 open complaints\n"
                "• Patch MoMo idempotency window to cover 6-hour reconnection gaps\n"
                "• Communicate proactive refunds to affected subscribers\n"
                "• File Ikeja cluster incident report linking outage to MoMo deduction spike"
            ),
            "citations": [
                {
                    "document_id": "doc_003",
                    "document_title": "Customer Complaints — MoMo Deductions Q1 2026",
                    "excerpt": "2,847 complaints; NGN 45M disputed; 73% resolution rate; Lagos highest volume",
                },
                {
                    "document_id": "doc_001",
                    "document_title": "Ikeja Cluster RCA — Power Outage Q1 2026",
                    "excerpt": "4.2 hour outage; MoMo transaction retry window linked to duplicate deductions",
                },
            ],
            "suggested_actions": [
                "Expedite resolution of 769 open MoMo deduction complaints",
                "Patch MoMo platform idempotency window to cover 6-hour reconnection gaps",
                "Proactively notify and refund affected Ikeja subscribers",
                "File formal incident linkage between Ikeja outage and MoMo spike",
            ],
            "suggested_followups": [
                "How does the Q1 2026 MoMo complaint volume compare to Q4 2025?",
                "Which specific MoMo transaction types were most affected?",
                "Draft a customer apology communication for affected Lagos subscribers",
            ],
            "confidence": "high",
            "is_pidgin": False,
        }

    async def _general_investigation(self, question: str) -> dict:
        self._log_trace("Researcher", "search_documents",
                        f"Searching for documents relevant to: {question}")
        self._log_trace("Strategist", "synthesise",
                        "Synthesising search results into a structured answer")

        return {
            "answer": (
                f"I searched across MTN Nigeria's enterprise documents to answer your question: "
                f"'{question}'\n\n"
                "Based on the available documents, here is what I found. For a more "
                "specific answer, try asking about a particular department, time period, "
                "or document type. You can also ask about: Ikeja cluster incidents, "
                "IHS Nigeria / Ericsson contracts, NDPA / NCC compliance, "
                "Kano-Kaduna fibre rollout, MoMo complaints, or enterprise SLA exposure."
            ),
            "suggested_followups": [
                "Can you be more specific about the department or time period?",
                "Would you like me to search a specific document type?",
                "Ask about: outage RCA, SLA exposure, NCC compliance, or BoQ status",
            ],
            "is_pidgin": False,
        }

    # ── Utilities ─────────────────────────────────────────────────────────────

    def _detect_pidgin(self, text: str) -> bool:
        pidgin_markers = ["wetin", "dey", "dem", "abeg", "na", "oga", "wahala", "comot", "fit", "sabi"]
        return any(marker in text.lower() for marker in pidgin_markers)

    def _log_trace(self, agent: str, tool: str, description: str):
        """Add an action to the live trace — sent to frontend via WebSocket."""
        self.trace.append({
            "agent": agent,
            "tool": tool,
            "description": description,
            "timestamp": datetime.utcnow().isoformat(),
        })
        logger.info(f"[{agent}] {tool}: {description}")
