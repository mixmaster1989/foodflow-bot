import logging
from enum import Enum
from typing import Optional

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import CanonicalProduct

logger = logging.getLogger(__name__)


class AnomalyDecision(str, Enum):
    OK = "ok"                       # Data looks healthy and realistic
    WARN_USER = "warn_user"         # Suspicious, but probably fine
    RECHECK_AI = "recheck_ai"       # Extreme values — AI should retry with strict prompt
    BLOCK = "block"                 # Complete hallucination


class NutritionResult(BaseModel):
    base_name: str
    display_name: str = ""
    calories: float
    protein: float
    fat: float
    carbs: float
    fiber: float
    weight_grams: Optional[float] = None  # Actual portion weight (None = per 100g)
    weight_missing: bool = False          # True if no weight was specified in query
    source: str                           # "cache", "normalization_service", "ai_failed"
    anomaly_status: AnomalyDecision
    warning_message: Optional[str] = None


class KBJUCoreService:
    """
    Core KBJU module.
    
    Flow:
    1. Normalize query → extract base_name
    2. Cache lookup in canonical_products
    3. If HIT → return cached values (scaled to portion weight if provided)
    4. If MISS → delegate to NormalizationService (existing battle-tested pipeline)
    5. Anomaly Guard validates result
    6. Save to cache (as per-100g etalon) if guard approves
    7. Return result (scaled to portion weight)
    """

    @classmethod
    async def get_product_nutrition(
        cls,
        query: str,
        db: AsyncSession,
        weight_grams: Optional[float] = None,
    ) -> NutritionResult:
        """
        Main entrypoint.
        
        Args:
            query: User's food description (e.g. "гречка", "банан 200г")
            db: Async DB session
            weight_grams: Optional pre-extracted weight in grams.
                          If None, the method will try NormalizationService
                          which extracts weight automatically.
        """
        normalized_query = query.strip().lower()

        # ── Step 1: Cache Lookup ──
        stmt = select(CanonicalProduct).where(
            CanonicalProduct.base_name == normalized_query
        )
        cached = (await db.execute(stmt)).scalar_one_or_none()

        if cached:
            logger.info(f"KBJUCore: CACHE HIT for '{normalized_query}'")
            return cls._build_result_from_cache(cached, weight_grams)

        logger.info(f"KBJUCore: CACHE MISS for '{normalized_query}'. Delegating to NormalizationService...")

        # ── Step 2: Delegate to NormalizationService ──
        raw = await cls._fetch_via_normalization(query)
        if not raw:
            return NutritionResult(
                base_name=normalized_query,
                calories=0.0, protein=0.0, fat=0.0, carbs=0.0, fiber=0.0,
                source="ai_failed",
                anomaly_status=AnomalyDecision.BLOCK,
                warning_message="Не удалось получить данные о продукте.",
            )

        # Extract weight from NormalizationService response if we don't have it
        effective_weight = weight_grams
        weight_missing = raw.get("weight_missing", True)

        if effective_weight is None and raw.get("weight_grams") and not weight_missing:
            # Only use AI weight if it explicitly says it's NOT missing (e.g. "1 apple" -> 150g)
            effective_weight = raw["weight_grams"]

        # Normalize to per-100g for caching
        per100 = cls._normalize_to_100g(raw, effective_weight)

        # ── Step 3: Anomaly Guard ──
        decision, warning = cls._anomaly_guard(per100)

        # ── Step 4: Save to Cache (only clean data) ──
        if decision in (AnomalyDecision.OK, AnomalyDecision.WARN_USER):
            await cls._save_to_cache(per100, db)

        # ── Step 5: Build final result (scaled to actual portion) ──
        return cls._build_result(
            per100, effective_weight, weight_missing, "normalization_service", decision, warning
        )

    # ──────────────────────────────────────────
    # Private: NormalizationService delegation
    # ──────────────────────────────────────────

    @classmethod
    async def _fetch_via_normalization(cls, query: str) -> Optional[dict]:
        """Delegate to the existing NormalizationService pipeline."""
        try:
            from services.normalization import NormalizationService
            result = await NormalizationService.analyze_food_intake(query)
            if result and "calories" in result:
                return result
        except Exception as e:
            logger.error(f"KBJUCore: NormalizationService delegation failed: {e}")
        return None

    # ──────────────────────────────────────────
    # Private: Normalization & Scaling
    # ──────────────────────────────────────────

    @classmethod
    def _normalize_to_100g(cls, raw: dict, weight_grams: Optional[float]) -> dict:
        """
        Convert NormalizationService output to per-100g etalon values.
        
        If weight_grams is known, the raw values represent that portion,
        so we divide by weight and multiply by 100 to get per-100g.
        
        If weight_missing=True, NormalizationService already returns per-100g.
        """
        base_name = raw.get("base_name", raw.get("name", "unknown")).strip().lower()
        
        cal = float(raw.get("calories") or 0)
        prot = float(raw.get("protein") or 0)
        fat = float(raw.get("fat") or 0)
        carbs = float(raw.get("carbs") or 0)
        fiber = float(raw.get("fiber") or 0)

        weight_missing = raw.get("weight_missing", True)

        if not weight_missing and weight_grams and weight_grams > 0:
            # Raw values are for the actual portion → convert to per-100g
            factor = 100.0 / weight_grams
            cal *= factor
            prot *= factor
            fat *= factor
            carbs *= factor
            fiber *= factor

        return {
            "base_name": base_name,
            "display_name": raw.get("name", base_name).strip(),
            "calories": round(cal, 1),
            "protein": round(prot, 1),
            "fat": round(fat, 1),
            "carbs": round(carbs, 1),
            "fiber": round(fiber, 1),
        }

    @classmethod
    def _build_result_from_cache(
        cls,
        cached: CanonicalProduct,
        weight_grams: Optional[float],
    ) -> NutritionResult:
        """Build NutritionResult from a cached canonical product, scaling to portion."""
        factor = (weight_grams / 100.0) if weight_grams else 1.0
        return NutritionResult(
            base_name=cached.base_name,
            display_name=cached.display_name or cached.base_name,
            calories=round(cached.calories * factor, 1),
            protein=round(cached.protein * factor, 1),
            fat=round(cached.fat * factor, 1),
            carbs=round(cached.carbs * factor, 1),
            fiber=round(cached.fiber * factor, 1),
            weight_grams=weight_grams,
            weight_missing=(weight_grams is None),
            source="cache",
            anomaly_status=AnomalyDecision.OK,
        )

    @classmethod
    def _build_result(
        cls,
        per100: dict,
        weight_grams: Optional[float],
        weight_missing: bool,
        source: str,
        decision: AnomalyDecision,
        warning: Optional[str],
    ) -> NutritionResult:
        """Build final NutritionResult, scaling per-100g etalon to actual portion."""
        factor = (weight_grams / 100.0) if weight_grams else 1.0
        return NutritionResult(
            base_name=per100["base_name"],
            display_name=per100.get("display_name", per100["base_name"]),
            calories=round(per100["calories"] * factor, 1),
            protein=round(per100["protein"] * factor, 1),
            fat=round(per100["fat"] * factor, 1),
            carbs=round(per100["carbs"] * factor, 1),
            fiber=round(per100["fiber"] * factor, 1),
            weight_grams=weight_grams,
            weight_missing=weight_missing,
            source=source,
            anomaly_status=decision,
            warning_message=warning,
        )

    # ──────────────────────────────────────────
    # Private: Anomaly Guard
    # ──────────────────────────────────────────

    @classmethod
    def _anomaly_guard(cls, per100: dict) -> tuple[AnomalyDecision, Optional[str]]:
        """Validate realistic per-100g KBJU ranges before caching."""
        c = per100.get("calories", 0)
        p = per100.get("protein", 0)
        f = per100.get("fat", 0)
        carbs = per100.get("carbs", 0)
        name = per100.get("base_name", "").lower()

        # 1. Mathematical consistency: macro formula
        expected_kcal = (p * 4) + (f * 9) + (carbs * 4)
        if expected_kcal > 0:
            diff = abs(c - expected_kcal) / expected_kcal
            if diff > 0.4:
                return (
                    AnomalyDecision.BLOCK,
                    f"⚠️ Неверное соотношение БЖУ и Ккал. Ожидалось ~{int(expected_kcal)}, получено {int(c)}.",
                )

        # 2. Hard limit: nothing in nature exceeds ~900 kcal / 100g
        if c > 910:
            return (
                AnomalyDecision.BLOCK,
                "⚠️ Калорийность >900 ккал/100г невозможна. Данные заблокированы.",
            )

        # 3. Warning: suspiciously high for non-fat/oil/nut products
        fat_words = ("масло", "жир", "орех", "семечк", "майонез", "сало")
        if c > 600 and not any(w in name for w in fat_words):
            return (
                AnomalyDecision.WARN_USER,
                "⚠️ Слишком калорийно для данной категории.",
            )

        # 4. Sum of macros can't exceed 100g in 100g of product
        if p + f + carbs > 105:  # small margin for rounding
            return (
                AnomalyDecision.BLOCK,
                "⚠️ Сумма макронутриентов >100г. Ошибка данных.",
            )

        return AnomalyDecision.OK, None

    # ──────────────────────────────────────────
    # Private: Cache Write
    # ──────────────────────────────────────────

    @classmethod
    async def _save_to_cache(cls, per100: dict, db: AsyncSession):
        """Save per-100g etalon to canonical_products (unverified, pending night audit)."""
        base = per100["base_name"].lower()
        
        # Double-check: don't overwrite a verified record
        stmt = select(CanonicalProduct).where(CanonicalProduct.base_name == base)
        existing = (await db.execute(stmt)).scalar_one_or_none()
        
        if existing:
            if existing.is_verified:
                logger.info(f"KBJUCore: Skipping cache write — '{base}' already verified.")
                return
            # Update unverified record with fresh data
            existing.calories = per100["calories"]
            existing.protein = per100["protein"]
            existing.fat = per100["fat"]
            existing.carbs = per100["carbs"]
            existing.fiber = per100["fiber"]
            existing.display_name = per100.get("display_name", base)
            existing.source = "normalization_service"
        else:
            new_record = CanonicalProduct(
                base_name=base,
                display_name=per100.get("display_name", base.capitalize()),
                calories=per100["calories"],
                protein=per100["protein"],
                fat=per100["fat"],
                carbs=per100["carbs"],
                fiber=per100["fiber"],
                source="normalization_service",
                per_unit="per_100g",
                is_verified=False,  # Pending night auditor verification
            )
            db.add(new_record)

        try:
            await db.commit()
            logger.info(f"KBJUCore: Cached '{base}' (is_verified=False, pending audit)")
        except Exception as e:
            await db.rollback()
            logger.warning(f"KBJUCore: Cache write failed for '{base}': {e}")
