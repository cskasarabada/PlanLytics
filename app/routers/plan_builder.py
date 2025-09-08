"""FastAPI router for plan building operations."""
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, Response, status, Query
from pydantic import BaseModel, Field

# Import guards ensure the router can be imported without hard dependencies
try:  # pragma: no cover - guard
    from ..core import composer, simulate as sim, optimize as opt
    from ..export import oracle_icm, excel_pack
except Exception:  # pragma: no cover - guard
    composer = sim = opt = oracle_icm = excel_pack = None  # type: ignore

router = APIRouter(prefix="/v1", tags=["plan-builder"])


class SuggestRequest(BaseModel):
    sales_goal: float = Field(..., example=1_000_000)
    num_reps: int = Field(..., example=10)


class SuggestResponse(BaseModel):
    plan_id: str
    details: Dict[str, Any]

    class Config:
        schema_extra = {
            "example": {
                "plan_id": "plan_10_100000",
                "details": {"quota_per_rep": 100000.0},
            }
        }


@router.post(
    "/plan/suggest",
    response_model=SuggestResponse,
    responses={
        400: {"description": "Invalid input"},
        503: {"description": "Composer module not available"},
    },
)
async def suggest_plan(payload: SuggestRequest) -> SuggestResponse:
    """Suggest a basic sales compensation plan."""
    if composer is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Composer module not available",
        )
    try:
        plan = composer.suggest_plan(payload.dict())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return SuggestResponse(**plan)


class SimulationRequest(BaseModel):
    plan_id: str = Field(..., example="plan_10_100000")
    performance: Dict[str, float] = Field(
        ..., example={"alice": 120000, "bob": 90000}
    )


class SimulationResponse(BaseModel):
    plan_id: str
    payouts: Dict[str, float]
    total_payout: float

    class Config:
        schema_extra = {
            "example": {
                "plan_id": "plan_10_100000",
                "payouts": {"alice": 12000.0, "bob": 9000.0},
                "total_payout": 21000.0,
            }
        }


@router.post(
    "/plan/simulate",
    response_model=SimulationResponse,
    responses={
        503: {"description": "Simulation module not available"},
    },
)
async def simulate_plan(payload: SimulationRequest) -> SimulationResponse:
    """Simulate payouts for a given plan."""
    if sim is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Simulation module not available",
        )
    result = sim.run_simulation(payload.plan_id, payload.performance)
    return SimulationResponse(**result)


class OptimizeRequest(BaseModel):
    plan_id: str = Field(..., example="plan_10_100000")
    target_rate: float = Field(0.1, example=0.12)


class OptimizeResponse(BaseModel):
    plan_id: str
    plan: Dict[str, Any]

    class Config:
        schema_extra = {
            "example": {
                "plan_id": "plan_10_100000",
                "plan": {"commission_rate": 0.12},
            }
        }


@router.post(
    "/plan/optimize",
    response_model=OptimizeResponse,
    responses={
        503: {"description": "Optimization module not available"},
    },
)
async def optimize_plan(payload: OptimizeRequest) -> OptimizeResponse:
    """Optimize plan parameters for provided objectives."""
    if opt is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Optimization module not available",
        )
    result = opt.optimize_plan(payload.plan_id, {"target_rate": payload.target_rate})
    return OptimizeResponse(**result)


class ExportICMRequest(BaseModel):
    plan_id: str = Field(..., example="plan_10_100000")


class ExportICMResponse(BaseModel):
    plan_id: str
    status: str
    system: str

    class Config:
        schema_extra = {
            "example": {
                "plan_id": "plan_10_100000",
                "status": "exported",
                "system": "oracle_icm",
            }
        }


@router.post(
    "/plan/export/icm",
    response_model=ExportICMResponse,
    responses={
        503: {"description": "ICM export module not available"},
    },
)
async def export_icm(payload: ExportICMRequest) -> ExportICMResponse:
    """Export a plan to an Oracle ICM friendly payload."""
    if oracle_icm is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ICM export module not available",
        )
    result = oracle_icm.export_plan_to_icm(payload.plan_id)
    return ExportICMResponse(**result)


@router.get(
    "/export/excel",
    responses={
        200: {
            "content": {
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {
                    "example": "UEsDBBQAAAAI"  # shortened base64 of XLSX header
                }
            },
            "description": "Binary Excel workbook",
        },
        503: {"description": "Excel export module not available"},
    },
)
async def export_excel(plan_id: str = Query(..., example="plan_10_100000")) -> Response:
    """Generate an Excel workbook for the plan."""
    if excel_pack is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Excel export module not available",
        )
    content = excel_pack.generate_workbook(plan_id)
    return Response(
        content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{plan_id}.xlsx"'
        },
    )
