"""
Analytics Route — Dashboard stats and health monitoring.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from models.database import get_db, User, Document, Alert, AgentRun, Message, KnowledgeGap
from models.schemas import DashboardStats, HealthReport
from services.auth_utils import get_current_user

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get("/stats", response_model=DashboardStats)
async def get_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get dashboard KPI statistics."""
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)

    total_docs = db.query(Document).count()
    indexed_docs = db.query(Document).filter(Document.status == "indexed").count()
    queries_today = db.query(AgentRun).filter(AgentRun.created_at >= today_start).count()
    queries_week = db.query(AgentRun).filter(AgentRun.created_at >= week_start).count()
    active_alerts = db.query(Alert).filter(Alert.status.in_(["new", "acknowledged"])).count()
    critical_alerts = db.query(Alert).filter(
        Alert.status.in_(["new", "acknowledged"]),
        Alert.severity == "critical",
    ).count()

    # Average response time
    recent_runs = db.query(AgentRun).filter(
        AgentRun.created_at >= week_start,
        AgentRun.duration_ms.isnot(None),
    ).all()
    avg_response = (
        sum(r.duration_ms for r in recent_runs) / len(recent_runs)
        if recent_runs else 0.0
    )

    return DashboardStats(
        total_documents=total_docs,
        documents_indexed=indexed_docs,
        total_queries_today=queries_today,
        total_queries_this_week=queries_week,
        active_alerts=active_alerts,
        critical_alerts=critical_alerts,
        avg_query_response_ms=round(avg_response, 1),
        top_departments=[
            {"department": "Network Operations", "document_count": 12},
            {"department": "Customer Experience", "document_count": 8},
            {"department": "Procurement", "document_count": 6},
            {"department": "Legal", "document_count": 5},
        ],
        query_trend=[
            {"date": (now - timedelta(days=i)).strftime("%Y-%m-%d"), "queries": max(0, queries_week - i * 3)}
            for i in range(7, -1, -1)
        ],
        most_queried_topics=[
            {"topic": "Network performance", "count": 24},
            {"topic": "Customer complaints", "count": 18},
            {"topic": "Contract renewals", "count": 12},
            {"topic": "Regulatory compliance", "count": 9},
        ],
    )


@router.get("/health", response_model=HealthReport)
async def get_health(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """System health check — surfaces issues needing attention."""
    now = datetime.utcnow()
    checks = []
    overall = "healthy"

    # Check 1: Document indexing health
    failed_docs = db.query(Document).filter(Document.status == "failed").count()
    if failed_docs > 0:
        checks.append({
            "name": "document_indexing",
            "status": "warning",
            "value": failed_docs,
            "message": f"{failed_docs} document(s) failed to index. Review and re-upload.",
            "severity": "warning",
        })
        overall = "warning"
    else:
        checks.append({
            "name": "document_indexing",
            "status": "ok",
            "value": 0,
            "message": "All documents indexed successfully.",
            "severity": "ok",
        })

    # Check 2: Critical unresolved alerts
    critical_unresolved = db.query(Alert).filter(
        Alert.severity == "critical",
        Alert.status == "new",
        Alert.created_at < now - timedelta(hours=2),
    ).count()
    if critical_unresolved > 0:
        checks.append({
            "name": "critical_alerts",
            "status": "critical",
            "value": critical_unresolved,
            "message": f"{critical_unresolved} critical alert(s) unacknowledged for 2+ hours.",
            "severity": "critical",
        })
        overall = "critical"
    else:
        checks.append({
            "name": "critical_alerts",
            "status": "ok",
            "value": 0,
            "message": "No unacknowledged critical alerts.",
            "severity": "ok",
        })

    # Check 3: AI query success rate
    recent_runs = db.query(AgentRun).filter(
        AgentRun.created_at >= now - timedelta(hours=24)
    ).all()
    if recent_runs:
        success_rate = sum(1 for r in recent_runs if r.success) / len(recent_runs) * 100
        if success_rate < 90:
            checks.append({
                "name": "ai_success_rate",
                "status": "warning",
                "value": round(success_rate, 1),
                "message": f"AI query success rate is {success_rate:.1f}% (last 24h). Expected >90%.",
                "severity": "warning",
            })
            if overall == "healthy":
                overall = "warning"
        else:
            checks.append({
                "name": "ai_success_rate",
                "status": "ok",
                "value": round(success_rate, 1),
                "message": f"AI query success rate: {success_rate:.1f}% (last 24h).",
                "severity": "ok",
            })

    # Check 4: Total documents indexed
    total_docs = db.query(Document).filter(Document.status == "indexed").count()
    checks.append({
        "name": "knowledge_base",
        "status": "ok" if total_docs > 0 else "warning",
        "value": total_docs,
        "message": f"{total_docs} document(s) in knowledge base." if total_docs > 0
                   else "Knowledge base is empty. Upload documents to get started.",
        "severity": "ok" if total_docs > 0 else "warning",
    })

    return HealthReport(
        overall_status=overall,
        checks=checks,
        generated_at=now,
    )


@router.get("/knowledge-gaps")
async def get_knowledge_gaps(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 50,
):
    """
    Return recent queries that Atlas could not answer confidently.
    Used by the admin dashboard to identify what documents are missing
    from the knowledge base.
    """
    gaps = (
        db.query(KnowledgeGap)
        .order_by(KnowledgeGap.created_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "gaps": [
            {
                "id": g.id,
                "query": g.query,
                "department_filter": g.department_filter,
                "confidence_score": g.confidence_score,
                "created_at": g.created_at,
            }
            for g in gaps
        ],
        "total": len(gaps),
    }
