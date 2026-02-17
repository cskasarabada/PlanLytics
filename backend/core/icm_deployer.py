# core/icm_deployer.py
"""
Bridge module that invokes ICM Optimizer managers to deploy the generated
Excel workbook to Oracle Fusion ICM via REST APIs.
"""
import sys
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Path to the ICM Optimizer repository
ICM_OPTIMIZER_PATH = "/Users/chandrak/ICM Optimizer"


def deploy_to_oracle_icm(
    excel_path: Path,
    config_path: Path,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Deploy ICM configuration from Excel workbook to Oracle ICM via ICM Optimizer.

    Args:
        excel_path: Path to the generated ICM workbook
        config_path: Path to ICM Optimizer config.yaml
        dry_run: If True, validate only without deploying

    Returns:
        Dict with deployment results per step
    """
    results: Dict[str, Any] = {"steps": [], "success": True}

    if dry_run:
        results["mode"] = "dry_run"
        results["message"] = "Validation only — no objects created in Oracle ICM"
        logger.info("Dry run: skipping actual deployment")
        return results

    # Add ICM Optimizer to Python path
    if ICM_OPTIMIZER_PATH not in sys.path:
        sys.path.insert(0, ICM_OPTIMIZER_PATH)

    try:
        from app.utils.api_client import APIClient
        from app.config.config_manager import ConfigManager
        from app.core.rate_dimension import RateDimensionManager
        from app.core.rate_table import RateTableManager
        from app.core.expression import ExpressionManager
        from app.core.performance_measure import PerformanceMeasureManager
        from app.core.plan_component import PlanComponentManager
        from app.core.compensation_plan import CompensationPlanManager
    except ImportError as e:
        results["success"] = False
        results["error"] = f"ICM Optimizer not found at {ICM_OPTIMIZER_PATH}: {e}"
        logger.error(results["error"])
        return results

    # Load config and initialize API client
    try:
        config_manager = ConfigManager(str(config_path))
        api_config = config_manager.get_section("api")
        api_client = APIClient(
            base_url=api_config["base_url"],
            username=api_config["username"],
            password=api_config["password"],
        )
    except Exception as e:
        results["success"] = False
        results["error"] = f"Failed to initialize API client: {e}"
        logger.error(results["error"])
        return results

    excel_str = str(excel_path)
    log_file = "objects_created.log"

    # Execute deployment in dependency order
    steps = [
        ("Rate Dimensions", lambda: RateDimensionManager(
            api_client, config_manager, log_file, excel_path=excel_str
        ).create_rate_dimensions(force=True)),
        ("Rate Tables", lambda: RateTableManager(
            api_client, config_manager, log_file, excel_path=excel_str
        ).create_rate_tables(force=True)),
        ("Expressions", lambda: ExpressionManager(
            api_client, config_manager, log_file, excel_path=excel_str
        ).configure_expressions(force=True)),
        ("Performance Measures", lambda: PerformanceMeasureManager(
            api_client, config_manager, log_file, excel_path=excel_str
        ).create_performance_measures(force=True)),
        ("Plan Components", lambda: PlanComponentManager(
            api_client, config_manager, log_file, excel_path=excel_str
        ).configure_plan_components(force=True)),
        ("Compensation Plans", lambda: CompensationPlanManager(
            api_client, config_manager, log_file, excel_path=excel_str
        ).create_compensation_plans_with_components(force=True)),
    ]

    for step_name, step_fn in steps:
        try:
            logger.info("Deploying: %s", step_name)
            success = step_fn()
            results["steps"].append({"name": step_name, "success": bool(success)})
            if not success:
                results["success"] = False
        except Exception as e:
            logger.exception("Deployment step '%s' failed: %s", step_name, e)
            results["steps"].append({
                "name": step_name, "success": False, "error": str(e),
            })
            results["success"] = False

    return results
