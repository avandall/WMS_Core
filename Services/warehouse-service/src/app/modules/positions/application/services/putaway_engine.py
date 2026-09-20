from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from app.shared.domain.business_exceptions import (
    InvalidIDError,
    InvalidQuantityError,
    ValidationError,
)


@dataclass
class PutawayRequest:
    """Request DTO containing product storage criteria for putaway suggestion."""

    product_id: int
    quantity: int
    unit_weight: float  # Weight per unit in kg
    unit_volume: float  # Volume per unit in m3
    abc_classification: str = "C"  # ABC velocity classification: "A", "B", "C"
    lot_number: Optional[str] = None
    preferred_position_type: str = "STORAGE"

    def __post_init__(self) -> None:
        if self.product_id <= 0:
            raise InvalidIDError("product_id must be positive")
        if self.quantity <= 0:
            raise InvalidQuantityError("quantity must be positive")
        if self.unit_weight < 0:
            raise InvalidQuantityError("unit_weight cannot be negative")
        if self.unit_volume < 0:
            raise InvalidQuantityError("unit_volume cannot be negative")
        if self.abc_classification not in {"A", "B", "C"}:
            raise ValidationError(f"Invalid ABC classification '{self.abc_classification}'")


@dataclass
class PositionCapacityInfo:
    """Information regarding a warehouse position's current load and capacity."""

    position_id: int
    code: str
    warehouse_id: int
    max_weight: float  # Maximum allowable weight in kg
    max_volume: float  # Maximum allowable volume in m3
    current_weight: float = 0.0  # Current total weight loaded in kg
    current_volume: float = 0.0  # Current total volume loaded in m3
    zone: str = "ZONE_C"  # ABC zone e.g., ZONE_A, ZONE_B, ZONE_C, or A, B, C
    position_type: str = "STORAGE"  # STORAGE, PICKING, QUARANTINE, DOCK
    is_active: bool = True

    def __post_init__(self) -> None:
        if self.position_id <= 0:
            raise InvalidIDError("position_id must be positive")
        if self.max_weight < 0 or self.max_volume < 0:
            raise InvalidQuantityError("Capacity limits must be non-negative")
        if self.current_weight < 0 or self.current_volume < 0:
            raise InvalidQuantityError("Current load values cannot be negative")

    @property
    def available_weight(self) -> float:
        return max(0.0, self.max_weight - self.current_weight)

    @property
    def available_volume(self) -> float:
        return max(0.0, self.max_volume - self.current_volume)

    def can_accommodate(self, required_weight: float, required_volume: float) -> bool:
        """Checks whether the position has sufficient weight and volume capacity."""
        if not self.is_active:
            return False
        return (
            self.available_weight >= required_weight
            and self.available_volume >= required_volume
        )


@dataclass
class PutawayRecommendation:
    """Result recommendation for cashing/putaway of an inbound product line."""

    position_id: int
    position_code: str
    zone: str
    recommended_qty: int
    score: float
    reason: str


class PutawayEngine:
    """Directed Putaway Engine prioritizing capacity limits (weight/volume) and ABC velocity zoning."""

    @staticmethod
    def suggest_putaway_location(
        request: PutawayRequest,
        candidate_positions: List[PositionCapacityInfo],
    ) -> List[PutawayRecommendation]:
        """Suggests optimal warehouse positions for storing requested product units.

        Filter logic:
        1. Position must be active and match preferred position type (e.g. STORAGE).
        2. Position available_weight >= required weight (unit_weight * quantity).
        3. Position available_volume >= required volume (unit_volume * quantity).

        Scoring & Ranking logic:
        - Zone match bonus: Higher score if position zone matches product's ABC classification.
          (A -> ZONE_A/A: +100, B -> ZONE_B/B: +80, C -> ZONE_C/C: +60)
        - Capacity utilization score: Prefers positions that efficiently utilize space without overloading.
        """
        required_total_weight = request.unit_weight * request.quantity
        required_total_volume = request.unit_volume * request.quantity

        recommendations: List[PutawayRecommendation] = []

        for pos in candidate_positions:
            if not pos.is_active:
                continue
            if pos.position_type.upper() != request.preferred_position_type.upper():
                continue
            if not pos.can_accommodate(required_total_weight, required_total_volume):
                continue

            score = PutawayEngine._calculate_score(request, pos, required_total_weight, required_total_volume)
            reason = PutawayEngine._build_reason(request, pos, score)

            recommendations.append(
                PutawayRecommendation(
                    position_id=pos.position_id,
                    position_code=pos.code,
                    zone=pos.zone,
                    recommended_qty=request.quantity,
                    score=score,
                    reason=reason,
                )
            )

        # Sort recommendations by score descending
        recommendations.sort(key=lambda r: r.score, reverse=True)
        return recommendations

    @staticmethod
    def _calculate_score(
        request: PutawayRequest,
        pos: PositionCapacityInfo,
        req_weight: float,
        req_volume: float,
    ) -> float:
        score = 0.0

        # ABC Velocity Zone alignment score
        abc = request.abc_classification.upper()
        pos_zone = pos.zone.upper()

        if (abc == "A" and ("ZONE_A" in pos_zone or pos_zone == "A")) or \
           (abc == "B" and ("ZONE_B" in pos_zone or pos_zone == "B")) or \
           (abc == "C" and ("ZONE_C" in pos_zone or pos_zone == "C")):
            score += 100.0
        elif (abc == "A" and ("ZONE_B" in pos_zone or pos_zone == "B")) or \
             (abc == "B" and ("ZONE_A" in pos_zone or pos_zone == "A" or "ZONE_C" in pos_zone or pos_zone == "C")):
            score += 50.0
        else:
            score += 20.0

        # Capacity utilization ratio preference (avoid empty vs overloaded extremes)
        if pos.max_volume > 0:
            vol_utilization = (pos.current_volume + req_volume) / pos.max_volume
            # Optimal utilization range is 40% - 85%
            score += (1.0 - abs(0.7 - vol_utilization)) * 20.0

        if pos.max_weight > 0:
            weight_utilization = (pos.current_weight + req_weight) / pos.max_weight
            score += (1.0 - abs(0.7 - weight_utilization)) * 20.0

        return round(score, 2)

    @staticmethod
    def _build_reason(request: PutawayRequest, pos: PositionCapacityInfo, score: float) -> str:
        abc = request.abc_classification.upper()
        pos_zone = pos.zone.upper()
        zone_matched = (abc in pos_zone or f"ZONE_{abc}" in pos_zone)
        match_str = "Exact ABC zone match" if zone_matched else "Secondary zone assignment"
        return f"{match_str} for ABC class '{abc}' in Zone '{pos.zone}'. Available weight: {pos.available_weight:.1f}kg, volume: {pos.available_volume:.2f}m3 (Score: {score})"
