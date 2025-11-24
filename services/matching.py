from datetime import datetime
from typing import Any

from rapidfuzz import fuzz
from sqlalchemy import select

from database.base import get_db
from database.models import LabelScan, Product, ShoppingSession


class MatchingService:
    MIN_SCORE = 70

    @staticmethod
    def _similarity(product_name: str, label: LabelScan) -> float:
        score = fuzz.WRatio(product_name, label.name)

        if label.weight and label.weight.lower() in product_name.lower():
            score = min(score + 5, 100)

        if label.brand and label.brand.lower() in product_name.lower():
            score = min(score + 5, 100)

        return score

    @staticmethod
    async def match_products(product_ids: list[int], session_id: int) -> dict[str, Any] | None:
        if not session_id or not product_ids:
            return None

        async for session in get_db():
            shopping_session = await session.get(ShoppingSession, session_id)
            if not shopping_session:
                return None

            label_stmt = select(LabelScan).where(LabelScan.session_id == session_id)
            label_result = await session.execute(label_stmt)
            label_scans = label_result.scalars().all()

            if not label_scans:
                shopping_session.is_active = False
                shopping_session.finished_at = datetime.utcnow()
                await session.commit()
                return None

            product_stmt = select(Product).where(Product.id.in_(product_ids))
            product_result = await session.execute(product_stmt)
            products = product_result.scalars().all()

            available_labels = [label for label in label_scans if not label.matched_product_id]

            matched_pairs = []
            unmatched_products = []
            used_label_ids: set[int] = set()

            for product in products:
                best_label = None
                best_score = 0

                for label in available_labels:
                    if label.id in used_label_ids:
                        continue

                    score = MatchingService._similarity(product.name, label)
                    if score >= MatchingService.MIN_SCORE and score > best_score:
                        best_label = label
                        best_score = score

                if best_label:
                    used_label_ids.add(best_label.id)
                    best_label.matched_product_id = product.id

                    if best_label.calories is not None:
                        product.calories = float(best_label.calories)
                    if best_label.protein is not None:
                        product.protein = float(best_label.protein)
                    if best_label.fat is not None:
                        product.fat = float(best_label.fat)
                    if best_label.carbs is not None:
                        product.carbs = float(best_label.carbs)

                    matched_pairs.append({
                        "product_id": product.id,
                        "product_name": product.name,
                        "label_id": best_label.id,
                        "label_name": best_label.name,
                        "score": best_score,
                        "brand": best_label.brand,
                        "weight": best_label.weight
                    })
                else:
                    unmatched_products.append(product)

            unmatched_labels = [
                label for label in label_scans
                if label.id not in used_label_ids and not label.matched_product_id
            ]

            suggestions: dict[int, list[dict[str, Any]]] = {}
            for product in unmatched_products:
                scored_labels = []
                for label in unmatched_labels:
                    score = MatchingService._similarity(product.name, label)
                    if score >= 40:  # provide broader hints
                        scored_labels.append((label, score))

                scored_labels.sort(key=lambda item: item[1], reverse=True)

                suggestions[product.id] = [
                    {
                        "label_id": label.id,
                        "label_name": label.name,
                        "brand": label.brand,
                        "weight": label.weight,
                        "score": score
                    }
                    for label, score in scored_labels[:3]
                ]

            shopping_session.is_active = False
            shopping_session.finished_at = datetime.utcnow()

            await session.commit()

            return {
                "matched": matched_pairs,
                "unmatched_products": [
                    {
                        "id": product.id,
                        "name": product.name,
                        "price": product.price,
                        "quantity": product.quantity,
                        "category": product.category
                    }
                    for product in unmatched_products
                ],
                "unmatched_labels": [
                    {
                        "id": label.id,
                        "name": label.name,
                        "brand": label.brand,
                        "weight": label.weight
                    }
                    for label in unmatched_labels
                ],
                "suggestions": suggestions
            }


