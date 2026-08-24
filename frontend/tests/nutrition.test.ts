import assert from 'node:assert/strict'

import {
    initializePortionNutrition,
    scalePortionNutrition,
    updatePortionNutritionField,
} from '../src/utils/nutrition'

const base = initializePortionNutrition({
    name: 'Шницель',
    weight_grams: 200,
    calories: 210,
    protein: 28,
    fat: 9,
    carbs: 6,
    fiber: 0.3,
})

assert.equal(base.calories, 420)
assert.equal(base.protein, 56)
assert.equal(base.calories_per_100g, 210)

const thirtySixGrams = scalePortionNutrition(base, 36)
assert.equal(thirtySixGrams.calories, 75.6)
assert.equal(thirtySixGrams.protein, 10.08)

const oneHundredGrams = scalePortionNutrition(thirtySixGrams, 100)
assert.equal(oneHundredGrams.calories, 210)
assert.equal(oneHundredGrams.fat, 9)

const editedAt200g = updatePortionNutritionField(base, 'calories', 500)
assert.equal(editedAt200g.calories, 500)
assert.equal(editedAt200g.calories_per_100g, 250)
assert.equal(scalePortionNutrition(editedAt200g, 50).calories, 125)

const missingWeight = initializePortionNutrition({
    calories: 52,
    protein: 0.3,
    fat: 0.2,
    carbs: 14,
    weight_grams: null,
})
assert.equal(missingWeight.calories, 52)
assert.equal(scalePortionNutrition(missingWeight, 250).calories, 130)

console.log('nutrition portion tests passed')
