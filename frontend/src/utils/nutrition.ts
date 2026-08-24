export type NutritionField = 'calories' | 'protein' | 'fat' | 'carbs' | 'fiber'

type NutritionInput = Record<string, unknown>

export type PortionNutrition = NutritionInput & {
    weight_grams: number
    calories: number
    protein: number
    fat: number
    carbs: number
    fiber: number
    calories_per_100g: number
    protein_per_100g: number
    fat_per_100g: number
    carbs_per_100g: number
    fiber_per_100g: number
}

const NUTRITION_FIELDS: NutritionField[] = [
    'calories',
    'protein',
    'fat',
    'carbs',
    'fiber',
]

const toFiniteNumber = (value: unknown): number => {
    const number = typeof value === 'number' ? value : Number(value)
    return Number.isFinite(number) ? number : 0
}

const roundNutrition = (value: number): number => Math.round(value * 1000) / 1000

const per100Key = (field: NutritionField) => `${field}_per_100g` as const

/**
 * Convert the normalizer response into the Mini App's explicit nutrition model.
 * The normalizer contract is KBJU per 100g plus a separate portion weight.
 */
export const initializePortionNutrition = (nutrition: NutritionInput): PortionNutrition => {
    const initialized = { ...nutrition } as PortionNutrition

    for (const field of NUTRITION_FIELDS) {
        const baseKey = per100Key(field)
        initialized[baseKey] = toFiniteNumber(nutrition[baseKey] ?? nutrition[field])
        initialized[field] = initialized[baseKey]
    }

    const weight = toFiniteNumber(nutrition.weight_grams)
    initialized.weight_grams = weight

    return weight > 0 ? scalePortionNutrition(initialized, weight) : initialized
}

/** Recalculate portion totals from immutable per-100g values. */
export const scalePortionNutrition = (
    nutrition: NutritionInput,
    weightGrams: number,
): PortionNutrition => {
    const weight = Math.max(0, toFiniteNumber(weightGrams))
    const factor = weight / 100
    const scaled = { ...nutrition, weight_grams: weight } as PortionNutrition

    for (const field of NUTRITION_FIELDS) {
        const baseKey = per100Key(field)
        const per100Value = toFiniteNumber(nutrition[baseKey] ?? nutrition[field])
        scaled[baseKey] = per100Value
        scaled[field] = roundNutrition(per100Value * factor)
    }

    return scaled
}

/**
 * Keep a manual KBJU correction stable across later weight edits by deriving
 * the corresponding per-100g value from the current portion.
 */
export const updatePortionNutritionField = (
    nutrition: NutritionInput,
    field: NutritionField,
    portionValue: number,
): PortionNutrition => {
    const value = Math.max(0, toFiniteNumber(portionValue))
    const weight = toFiniteNumber(nutrition.weight_grams)
    const factor = weight > 0 ? weight / 100 : 1

    return {
        ...nutrition,
        [field]: value,
        [per100Key(field)]: roundNutrition(value / factor),
    } as PortionNutrition
}
