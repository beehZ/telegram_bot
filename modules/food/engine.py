import logging
from typing import Optional

from modules.food.parser import FoodParser, ParsedFoodItem

logger = logging.getLogger("food.engine")

PER_100ML_CAL = 0.6
PER_100G_CAL = 1.0

FOOD_DB: dict[str, dict] = {
    "coffee": {"calories": 2, "protein": 0.1, "fat": 0, "carbs": 0, "sugar": 0, "fiber": 0, "base": "100ml", "vitamins": []},
    "kofe": {"calories": 2, "protein": 0.1, "fat": 0, "carbs": 0, "sugar": 0, "fiber": 0, "base": "100ml", "vitamins": []},
    "tea": {"calories": 1, "protein": 0, "fat": 0, "carbs": 0, "sugar": 0, "fiber": 0, "base": "100ml", "vitamins": []},
    "choy": {"calories": 1, "protein": 0, "fat": 0, "carbs": 0, "sugar": 0, "fiber": 0, "base": "100ml", "vitamins": []},
    "suv": {"calories": 0, "protein": 0, "fat": 0, "carbs": 0, "sugar": 0, "fiber": 0, "base": "100ml", "vitamins": []},
    "water": {"calories": 0, "protein": 0, "fat": 0, "carbs": 0, "sugar": 0, "fiber": 0, "base": "100ml", "vitamins": []},
    "cola": {"calories": 42, "protein": 0, "fat": 0, "carbs": 10.6, "sugar": 10.6, "fiber": 0, "base": "100ml", "vitamins": []},
    "fanta": {"calories": 48, "protein": 0, "fat": 0, "carbs": 12, "sugar": 12, "fiber": 0, "base": "100ml", "vitamins": []},
    "sprite": {"calories": 40, "protein": 0, "fat": 0, "carbs": 10, "sugar": 10, "fiber": 0, "base": "100ml", "vitamins": []},
    "pepsi": {"calories": 41, "protein": 0, "fat": 0, "carbs": 10.3, "sugar": 10.3, "fiber": 0, "base": "100ml", "vitamins": []},
    "juice": {"calories": 45, "protein": 0.5, "fat": 0, "carbs": 11, "sugar": 10, "fiber": 0, "base": "100ml", "vitamins": ["Vitamin C"]},
    "sharbat": {"calories": 45, "protein": 0.5, "fat": 0, "carbs": 11, "sugar": 10, "fiber": 0, "base": "100ml", "vitamins": ["Vitamin C"]},
    "sok": {"calories": 45, "protein": 0.5, "fat": 0, "carbs": 11, "sugar": 10, "fiber": 0, "base": "100ml", "vitamins": ["Vitamin C"]},
    "sut": {"calories": 61, "protein": 3.2, "fat": 3.5, "carbs": 4.8, "sugar": 4.8, "fiber": 0, "base": "100ml", "vitamins": ["Calcium", "Vitamin D", "Vitamin B12"]},
    "milk": {"calories": 61, "protein": 3.2, "fat": 3.5, "carbs": 4.8, "sugar": 4.8, "fiber": 0, "base": "100ml", "vitamins": ["Calcium", "Vitamin D", "Vitamin B12"]},
    "kefir": {"calories": 40, "protein": 3.5, "fat": 1, "carbs": 4, "sugar": 4, "fiber": 0, "base": "100ml", "vitamins": ["Calcium", "Vitamin B12"]},
    "ayran": {"calories": 30, "protein": 1.5, "fat": 1.5, "carbs": 2.5, "sugar": 2.5, "fiber": 0, "base": "100ml", "vitamins": ["Calcium"]},
    "qatiq": {"calories": 60, "protein": 3.5, "fat": 3, "carbs": 4.5, "sugar": 4.5, "fiber": 0, "base": "100g", "vitamins": ["Calcium", "Probiotics"]},
    "yogurt": {"calories": 60, "protein": 3.5, "fat": 3, "carbs": 4.5, "sugar": 4.5, "fiber": 0, "base": "100g", "vitamins": ["Calcium", "Probiotics"]},
    "tuxum": {"calories": 70, "protein": 6, "fat": 5, "carbs": 0.6, "sugar": 0, "fiber": 0, "base": "piece", "vitamins": ["Vitamin B12", "Vitamin D", "Choline"]},
    "egg": {"calories": 70, "protein": 6, "fat": 5, "carbs": 0.6, "sugar": 0, "fiber": 0, "base": "piece", "vitamins": ["Vitamin B12", "Vitamin D", "Choline"]},
    "non": {"calories": 265, "protein": 8, "fat": 3, "carbs": 49, "sugar": 3, "fiber": 2.5, "base": "100g", "vitamins": ["Vitamin B1", "Iron"]},
    "bread": {"calories": 265, "protein": 8, "fat": 3, "carbs": 49, "sugar": 3, "fiber": 2.5, "base": "100g", "vitamins": ["Vitamin B1", "Iron"]},
    "banan": {"calories": 89, "protein": 1.1, "fat": 0.3, "carbs": 23, "sugar": 12, "fiber": 2.6, "base": "piece", "vitamins": ["Vitamin B6", "Vitamin C", "Potassium"]},
    "banana": {"calories": 89, "protein": 1.1, "fat": 0.3, "carbs": 23, "sugar": 12, "fiber": 2.6, "base": "piece", "vitamins": ["Vitamin B6", "Vitamin C", "Potassium"]},
    "olma": {"calories": 52, "protein": 0.3, "fat": 0.2, "carbs": 14, "sugar": 10, "fiber": 2.4, "base": "piece", "vitamins": ["Vitamin C"]},
    "apple": {"calories": 52, "protein": 0.3, "fat": 0.2, "carbs": 14, "sugar": 10, "fiber": 2.4, "base": "piece", "vitamins": ["Vitamin C"]},
    "nok": {"calories": 57, "protein": 0.4, "fat": 0.1, "carbs": 15, "sugar": 10, "fiber": 3.1, "base": "piece", "vitamins": ["Vitamin C", "Vitamin K"]},
    "pear": {"calories": 57, "protein": 0.4, "fat": 0.1, "carbs": 15, "sugar": 10, "fiber": 3.1, "base": "piece", "vitamins": ["Vitamin C", "Vitamin K"]},
    "apelsin": {"calories": 47, "protein": 0.9, "fat": 0.1, "carbs": 12, "sugar": 9, "fiber": 2.4, "base": "piece", "vitamins": ["Vitamin C"]},
    "orange": {"calories": 47, "protein": 0.9, "fat": 0.1, "carbs": 12, "sugar": 9, "fiber": 2.4, "base": "piece", "vitamins": ["Vitamin C"]},
    "mandarin": {"calories": 53, "protein": 0.8, "fat": 0.3, "carbs": 13, "sugar": 11, "fiber": 1.8, "base": "piece", "vitamins": ["Vitamin C"]},
    "uzum": {"calories": 69, "protein": 0.7, "fat": 0.2, "carbs": 18, "sugar": 16, "fiber": 0.9, "base": "100g", "vitamins": ["Vitamin C", "Vitamin K"]},
    "grape": {"calories": 69, "protein": 0.7, "fat": 0.2, "carbs": 18, "sugar": 16, "fiber": 0.9, "base": "100g", "vitamins": ["Vitamin C", "Vitamin K"]},
    "qulupnay": {"calories": 32, "protein": 0.7, "fat": 0.3, "carbs": 8, "sugar": 5, "fiber": 2, "base": "100g", "vitamins": ["Vitamin C"]},
    "strawberry": {"calories": 32, "protein": 0.7, "fat": 0.3, "carbs": 8, "sugar": 5, "fiber": 2, "base": "100g", "vitamins": ["Vitamin C"]},
    "gilos": {"calories": 50, "protein": 1, "fat": 0.3, "carbs": 12, "sugar": 8, "fiber": 1.6, "base": "100g", "vitamins": ["Vitamin C"]},
    "tarvuz": {"calories": 30, "protein": 0.6, "fat": 0.2, "carbs": 8, "sugar": 6, "fiber": 0.4, "base": "100g", "vitamins": ["Vitamin C", "Vitamin A"]},
    "watermelon": {"calories": 30, "protein": 0.6, "fat": 0.2, "carbs": 8, "sugar": 6, "fiber": 0.4, "base": "100g", "vitamins": ["Vitamin C", "Vitamin A"]},
    "qovun": {"calories": 34, "protein": 0.8, "fat": 0.2, "carbs": 8, "sugar": 8, "fiber": 0.9, "base": "100g", "vitamins": ["Vitamin C", "Vitamin A"]},
    "shaftoli": {"calories": 39, "protein": 0.9, "fat": 0.3, "carbs": 10, "sugar": 8, "fiber": 1.5, "base": "piece", "vitamins": ["Vitamin C", "Vitamin A"]},
    "peach": {"calories": 39, "protein": 0.9, "fat": 0.3, "carbs": 10, "sugar": 8, "fiber": 1.5, "base": "piece", "vitamins": ["Vitamin C", "Vitamin A"]},
    "guruch": {"calories": 130, "protein": 2.7, "fat": 0.3, "carbs": 28, "sugar": 0, "fiber": 0.4, "base": "100g", "vitamins": []},
    "rice": {"calories": 130, "protein": 2.7, "fat": 0.3, "carbs": 28, "sugar": 0, "fiber": 0.4, "base": "100g", "vitamins": []},
    "kartoshka": {"calories": 77, "protein": 2, "fat": 0.1, "carbs": 17, "sugar": 1, "fiber": 2.2, "base": "100g", "vitamins": ["Vitamin C", "Potassium", "Vitamin B6"]},
    "potato": {"calories": 77, "protein": 2, "fat": 0.1, "carbs": 17, "sugar": 1, "fiber": 2.2, "base": "100g", "vitamins": ["Vitamin C", "Potassium", "Vitamin B6"]},
    "go'sht": {"calories": 250, "protein": 26, "fat": 15, "carbs": 0, "sugar": 0, "fiber": 0, "base": "100g", "vitamins": ["Vitamin B12", "Iron", "Zinc"]},
    "mol go'sht": {"calories": 250, "protein": 26, "fat": 15, "carbs": 0, "sugar": 0, "fiber": 0, "base": "100g", "vitamins": ["Vitamin B12", "Iron", "Zinc"]},
    "qo'y go'sht": {"calories": 294, "protein": 25, "fat": 21, "carbs": 0, "sugar": 0, "fiber": 0, "base": "100g", "vitamins": ["Vitamin B12", "Iron", "Zinc"]},
    "tovuq": {"calories": 165, "protein": 31, "fat": 3.6, "carbs": 0, "sugar": 0, "fiber": 0, "base": "100g", "vitamins": ["Vitamin B6", "Niacin", "Phosphorus"]},
    "chicken": {"calories": 165, "protein": 31, "fat": 3.6, "carbs": 0, "sugar": 0, "fiber": 0, "base": "100g", "vitamins": ["Vitamin B6", "Niacin", "Phosphorus"]},
    "kurka": {"calories": 135, "protein": 30, "fat": 1.5, "carbs": 0, "sugar": 0, "fiber": 0, "base": "100g", "vitamins": ["Vitamin B6", "Niacin"]},
    "baliq": {"calories": 200, "protein": 22, "fat": 12, "carbs": 0, "sugar": 0, "fiber": 0, "base": "100g", "vitamins": ["Vitamin D", "Omega-3", "Vitamin B12"]},
    "fish": {"calories": 200, "protein": 22, "fat": 12, "carbs": 0, "sugar": 0, "fiber": 0, "base": "100g", "vitamins": ["Vitamin D", "Omega-3", "Vitamin B12"]},
    "krevetka": {"calories": 85, "protein": 18, "fat": 0.8, "carbs": 0, "sugar": 0, "fiber": 0, "base": "100g", "vitamins": ["Vitamin B12", "Iron"]},
    "shurva": {"calories": 60, "protein": 4, "fat": 3, "carbs": 5, "sugar": 1, "fiber": 0.5, "base": "100ml", "vitamins": ["Vitamin A", "Vitamin C", "Iron"]},
    "soup": {"calories": 50, "protein": 3, "fat": 2, "carbs": 5, "sugar": 1, "fiber": 0.5, "base": "100ml", "vitamins": ["Vitamin A", "Vitamin C"]},
    "mastava": {"calories": 55, "protein": 3, "fat": 1.5, "carbs": 8, "sugar": 1, "fiber": 0.5, "base": "100ml", "vitamins": ["Vitamin A", "Vitamin C"]},
    "osh": {"calories": 170, "protein": 5, "fat": 5, "carbs": 26, "sugar": 1, "fiber": 0.5, "base": "100g", "vitamins": ["Vitamin A", "Iron"]},
    "palov": {"calories": 170, "protein": 5, "fat": 5, "carbs": 26, "sugar": 1, "fiber": 0.5, "base": "100g", "vitamins": ["Vitamin A", "Iron"]},
    "plov": {"calories": 170, "protein": 5, "fat": 5, "carbs": 26, "sugar": 1, "fiber": 0.5, "base": "100g", "vitamins": ["Vitamin A", "Iron"]},
    "manti": {"calories": 180, "protein": 10, "fat": 8, "carbs": 18, "sugar": 1, "fiber": 1, "base": "piece", "vitamins": ["Iron", "Vitamin B12"]},
    "somsa": {"calories": 220, "protein": 8, "fat": 12, "carbs": 25, "sugar": 1, "fiber": 1, "base": "piece", "vitamins": ["Iron"]},
    "lagman": {"calories": 100, "protein": 5, "fat": 3, "carbs": 14, "sugar": 1, "fiber": 0.5, "base": "100g", "vitamins": ["Vitamin A", "Vitamin C", "Iron"]},
    "kebab": {"calories": 200, "protein": 20, "fat": 12, "carbs": 2, "sugar": 0, "fiber": 0, "base": "100g", "vitamins": ["Vitamin B12", "Iron"]},
    "kabob": {"calories": 200, "protein": 20, "fat": 12, "carbs": 2, "sugar": 0, "fiber": 0, "base": "100g", "vitamins": ["Vitamin B12", "Iron"]},
    "burger": {"calories": 250, "protein": 13, "fat": 12, "carbs": 25, "sugar": 5, "fiber": 1, "base": "100g", "vitamins": ["Calcium", "Iron"]},
    "pizza": {"calories": 266, "protein": 11, "fat": 10, "carbs": 33, "sugar": 4, "fiber": 2, "base": "100g", "vitamins": ["Calcium", "Vitamin A"]},
    "shashlik": {"calories": 200, "protein": 22, "fat": 12, "carbs": 2, "sugar": 0, "fiber": 0, "base": "100g", "vitamins": ["Vitamin B12", "Iron"]},
    "pishloq": {"calories": 350, "protein": 25, "fat": 27, "carbs": 1.3, "sugar": 0.5, "fiber": 0, "base": "100g", "vitamins": ["Calcium", "Vitamin B12"]},
    "cheese": {"calories": 350, "protein": 25, "fat": 27, "carbs": 1.3, "sugar": 0.5, "fiber": 0, "base": "100g", "vitamins": ["Calcium", "Vitamin B12"]},
    "suzma": {"calories": 120, "protein": 15, "fat": 6, "carbs": 2, "sugar": 2, "fiber": 0, "base": "100g", "vitamins": ["Calcium"]},
    "qaymoq": {"calories": 340, "protein": 2.5, "fat": 36, "carbs": 3, "sugar": 3, "fiber": 0, "base": "100g", "vitamins": ["Vitamin A"]},
    "sabzi": {"calories": 41, "protein": 0.9, "fat": 0.2, "carbs": 10, "sugar": 5, "fiber": 2.8, "base": "100g", "vitamins": ["Vitamin A", "Vitamin K"]},
    "carrot": {"calories": 41, "protein": 0.9, "fat": 0.2, "carbs": 10, "sugar": 5, "fiber": 2.8, "base": "100g", "vitamins": ["Vitamin A", "Vitamin K"]},
    "bodring": {"calories": 15, "protein": 0.7, "fat": 0.1, "carbs": 3.6, "sugar": 1.7, "fiber": 0.5, "base": "100g", "vitamins": ["Vitamin K"]},
    "cucumber": {"calories": 15, "protein": 0.7, "fat": 0.1, "carbs": 3.6, "sugar": 1.7, "fiber": 0.5, "base": "100g", "vitamins": ["Vitamin K"]},
    "pomidor": {"calories": 18, "protein": 0.9, "fat": 0.2, "carbs": 3.9, "sugar": 2.6, "fiber": 1.2, "base": "100g", "vitamins": ["Vitamin C", "Vitamin K"]},
    "tomato": {"calories": 18, "protein": 0.9, "fat": 0.2, "carbs": 3.9, "sugar": 2.6, "fiber": 1.2, "base": "100g", "vitamins": ["Vitamin C", "Vitamin K"]},
    "piyoz": {"calories": 40, "protein": 1.1, "fat": 0.1, "carbs": 9, "sugar": 4, "fiber": 1.7, "base": "100g", "vitamins": ["Vitamin C", "Vitamin B6"]},
    "onion": {"calories": 40, "protein": 1.1, "fat": 0.1, "carbs": 9, "sugar": 4, "fiber": 1.7, "base": "100g", "vitamins": ["Vitamin C", "Vitamin B6"]},
    "kuk choy": {"calories": 5, "protein": 0.5, "fat": 0, "carbs": 1, "sugar": 0, "fiber": 0.5, "base": "100g", "vitamins": ["Vitamin C", "Vitamin A"]},
    "ko'k": {"calories": 5, "protein": 0.5, "fat": 0, "carbs": 1, "sugar": 0, "fiber": 0.5, "base": "100g", "vitamins": ["Vitamin C", "Vitamin A"]},
    "salat": {"calories": 15, "protein": 1, "fat": 0.2, "carbs": 2.9, "sugar": 1, "fiber": 1.5, "base": "100g", "vitamins": ["Vitamin A", "Vitamin K"]},
    "karam": {"calories": 25, "protein": 1.3, "fat": 0.1, "carbs": 6, "sugar": 3, "fiber": 2.5, "base": "100g", "vitamins": ["Vitamin C", "Vitamin K"]},
    "cabbage": {"calories": 25, "protein": 1.3, "fat": 0.1, "carbs": 6, "sugar": 3, "fiber": 2.5, "base": "100g", "vitamins": ["Vitamin C", "Vitamin K"]},
    "sholg'om": {"calories": 28, "protein": 0.9, "fat": 0.1, "carbs": 6, "sugar": 4, "fiber": 1.8, "base": "100g", "vitamins": ["Vitamin C"]},
    "lavlagi": {"calories": 43, "protein": 1.6, "fat": 0.2, "carbs": 10, "sugar": 7, "fiber": 2.8, "base": "100g", "vitamins": ["Folate", "Vitamin C"]},
    "beetroot": {"calories": 43, "protein": 1.6, "fat": 0.2, "carbs": 10, "sugar": 7, "fiber": 2.8, "base": "100g", "vitamins": ["Folate", "Vitamin C"]},
    "qalampir": {"calories": 26, "protein": 1, "fat": 0.3, "carbs": 6, "sugar": 4, "fiber": 2.1, "base": "100g", "vitamins": ["Vitamin C", "Vitamin A"]},
    "mosh": {"calories": 347, "protein": 24, "fat": 1.2, "carbs": 63, "sugar": 2, "fiber": 16, "base": "100g", "vitamins": ["Folate", "Iron"]},
    "loviya": {"calories": 132, "protein": 8.7, "fat": 0.5, "carbs": 24, "sugar": 0.3, "fiber": 6.4, "base": "100g", "vitamins": ["Iron", "Folate"]},
    "no'xat": {"calories": 139, "protein": 8.2, "fat": 0.6, "carbs": 23, "sugar": 3, "fiber": 5.5, "base": "100g", "vitamins": ["Iron", "Folate"]},
    "shokolad": {"calories": 546, "protein": 4.9, "fat": 31, "carbs": 61, "sugar": 48, "fiber": 3.4, "base": "100g", "vitamins": []},
    "chocolate": {"calories": 546, "protein": 4.9, "fat": 31, "carbs": 61, "sugar": 48, "fiber": 3.4, "base": "100g", "vitamins": []},
    "konfet": {"calories": 400, "protein": 2, "fat": 10, "carbs": 80, "sugar": 70, "fiber": 0.5, "base": "100g", "vitamins": []},
    "pechenye": {"calories": 450, "protein": 6, "fat": 18, "carbs": 68, "sugar": 25, "fiber": 2, "base": "100g", "vitamins": []},
    "cookie": {"calories": 450, "protein": 6, "fat": 18, "carbs": 68, "sugar": 25, "fiber": 2, "base": "100g", "vitamins": []},
    "cake": {"calories": 350, "protein": 4, "fat": 15, "carbs": 52, "sugar": 35, "fiber": 1, "base": "100g", "vitamins": ["Calcium"]},
    "tort": {"calories": 350, "protein": 4, "fat": 15, "carbs": 52, "sugar": 35, "fiber": 1, "base": "100g", "vitamins": ["Calcium"]},
    "pirog": {"calories": 280, "protein": 5, "fat": 12, "carbs": 38, "sugar": 10, "fiber": 1, "base": "100g", "vitamins": []},
    "kolbasa": {"calories": 300, "protein": 12, "fat": 27, "carbs": 2, "sugar": 1, "fiber": 0, "base": "100g", "vitamins": ["Vitamin B12", "Iron"]},
    "sosiska": {"calories": 250, "protein": 10, "fat": 22, "carbs": 3, "sugar": 1, "fiber": 0, "base": "100g", "vitamins": []},
    "asal": {"calories": 304, "protein": 0.3, "fat": 0, "carbs": 82, "sugar": 82, "fiber": 0, "base": "100g", "vitamins": []},
    "honey": {"calories": 304, "protein": 0.3, "fat": 0, "carbs": 82, "sugar": 82, "fiber": 0, "base": "100g", "vitamins": []},
    "murabbo": {"calories": 250, "protein": 0.3, "fat": 0, "carbs": 65, "sugar": 60, "fiber": 0.5, "base": "100g", "vitamins": []},
    "jam": {"calories": 250, "protein": 0.3, "fat": 0, "carbs": 65, "sugar": 60, "fiber": 0.5, "base": "100g", "vitamins": []},
    "sariyog'": {"calories": 717, "protein": 0.9, "fat": 81, "carbs": 0, "sugar": 0, "fiber": 0, "base": "100g", "vitamins": ["Vitamin A"]},
    "butter": {"calories": 717, "protein": 0.9, "fat": 81, "carbs": 0, "sugar": 0, "fiber": 0, "base": "100g", "vitamins": ["Vitamin A"]},
    "yog'": {"calories": 884, "protein": 0, "fat": 100, "carbs": 0, "sugar": 0, "fiber": 0, "base": "100g", "vitamins": ["Vitamin E"]},
    "oil": {"calories": 884, "protein": 0, "fat": 100, "carbs": 0, "sugar": 0, "fiber": 0, "base": "100g", "vitamins": ["Vitamin E"]},
    "makaron": {"calories": 131, "protein": 5, "fat": 1, "carbs": 25, "sugar": 1, "fiber": 1.5, "base": "100g", "vitamins": []},
    "pasta": {"calories": 131, "protein": 5, "fat": 1, "carbs": 25, "sugar": 1, "fiber": 1.5, "base": "100g", "vitamins": []},
    "spagetti": {"calories": 158, "protein": 5.8, "fat": 0.9, "carbs": 31, "sugar": 1, "fiber": 1.8, "base": "100g", "vitamins": []},
    "yorma": {"calories": 123, "protein": 3.5, "fat": 0.5, "carbs": 26, "sugar": 0.5, "fiber": 1.3, "base": "100g", "vitamins": ["Vitamin B1"]},
    "moshkichiri": {"calories": 160, "protein": 7, "fat": 3, "carbs": 27, "sugar": 1, "fiber": 4, "base": "100g", "vitamins": ["Iron", "Folate"]},
    "grechka": {"calories": 110, "protein": 4, "fat": 1, "carbs": 23, "sugar": 0.5, "fiber": 2.5, "base": "100g", "vitamins": ["Vitamin B1", "Iron"]},
    "suli": {"calories": 68, "protein": 2.5, "fat": 1.4, "carbs": 12, "sugar": 0.5, "fiber": 1.7, "base": "100g", "vitamins": []},
    "oatmeal": {"calories": 68, "protein": 2.5, "fat": 1.4, "carbs": 12, "sugar": 0.5, "fiber": 1.7, "base": "100g", "vitamins": []},
    "muesli": {"calories": 180, "protein": 4, "fat": 3, "carbs": 35, "sugar": 12, "fiber": 4, "base": "100g", "vitamins": ["Vitamin B1"]},
    "chips": {"calories": 536, "protein": 7, "fat": 35, "carbs": 49, "sugar": 5, "fiber": 3, "base": "100g", "vitamins": []},
    "qazi": {"calories": 350, "protein": 15, "fat": 32, "carbs": 0, "sugar": 0, "fiber": 0, "base": "100g", "vitamins": ["Vitamin B12"]},
    "kazi": {"calories": 350, "protein": 15, "fat": 32, "carbs": 0, "sugar": 0, "fiber": 0, "base": "100g", "vitamins": ["Vitamin B12"]},
}

FOOD_DB_ALIASES: dict[str, str] = {
    "kartoshka fri": "kartoshka",
    "french fries": "kartoshka",
    "qovurilgan kartoshka": "kartoshka",
    "dymlena kolbasa": "kolbasa",
    "varenaya kolbasa": "kolbasa",
    "tovuq go'sht": "tovuq",
    "kurka go'sht": "kurka",
    "mol go'shti": "go'sht",
    "sutli coctail": "sut",
    "milkshake": "sut",
    "olma sharbat": "sharbat",
    "apelsin sharbat": "apelsin",
    "tuxum oqsil": "tuxum",
}

AVG_FOOD_CALORIES_PER_100 = 150
AVG_FOOD_PROTEIN_PER_100 = 5
AVG_FOOD_FAT_PER_100 = 5
AVG_FOOD_CARBS_PER_100 = 20

UNIT_TO_100G_FACTOR: dict[str, float] = {
    "ml": 0.01,
    "g": 0.01,
    "kg": 10,
    "liter": 10,
    "litr": 10,
    "l": 10,
    "cup": 2.4,
    "stakan": 2.4,
    "glass": 2.4,
    "chashka": 2.4,
    "piyola": 2.0,
    "spoon": 0.15,
    "tbsp": 0.15,
    "tsp": 0.05,
    "qoshiq": 0.15,
    "bottle": 5.0,
    "shisha": 5.0,
    "butilka": 5.0,
    "slice": 0.3,
    "bo'lak": 1.0,
    "tilim": 0.3,
    "dilim": 0.3,
    "piece": 1.5,
    "dona": 1.5,
    "ta": 1.5,
}


class AggregatedNutrition:
    def __init__(self):
        self.calories = 0
        self.protein = 0.0
        self.fat = 0.0
        self.carbs = 0.0
        self.sugar = 0.0
        self.fiber = 0.0
        self.vitamins: list[str] = []
        self.items: list[dict] = []

    def add(self, nutrition: dict, food_name: str, amount: float, unit: str):
        self.calories += nutrition.get("calories", 0)
        self.protein += nutrition.get("protein", 0)
        self.fat += nutrition.get("fat", 0)
        self.carbs += nutrition.get("carbs", 0)
        self.sugar += nutrition.get("sugar", 0)
        self.fiber += nutrition.get("fiber", 0)
        for v in nutrition.get("vitamins", []):
            if v not in self.vitamins:
                self.vitamins.append(v)
        self.items.append({
            "food": food_name,
            "amount": amount,
            "unit": unit,
            "nutrition": nutrition,
        })


class NutritionEngine:
    def __init__(self):
        self.parser = FoodParser

    def _resolve_alias(self, food_name: str) -> str:
        fn = food_name.strip().lower()
        if fn in FOOD_DB_ALIASES:
            return FOOD_DB_ALIASES[fn]
        for alias, target in FOOD_DB_ALIASES.items():
            if fn == alias or fn.endswith(" " + alias) or fn.startswith(alias + " "):
                return target
        return fn

    def _lookup_local(self, food_name: str) -> Optional[dict]:
        fn = self._resolve_alias(food_name)
        if fn in FOOD_DB:
            return dict(FOOD_DB[fn])
        for key, val in FOOD_DB.items():
            if key == fn:
                return dict(val)
            if len(fn) >= 5 and len(key) >= 3:
                if key in fn or fn in key:
                    return dict(val)
        return None

    def _fallback_estimate(self, amount: float, unit: str) -> dict:
        factor = UNIT_TO_100G_FACTOR.get(unit, 0.1)
        rel = amount * factor
        return {
            "calories": round(AVG_FOOD_CALORIES_PER_100 * rel),
            "protein": round(AVG_FOOD_PROTEIN_PER_100 * rel, 1),
            "fat": round(AVG_FOOD_FAT_PER_100 * rel, 1),
            "carbs": round(AVG_FOOD_CARBS_PER_100 * rel, 1),
            "sugar": 0,
            "fiber": 0,
            "vitamins": [],
            "_estimated": True,
        }

    def _scale_nutrition(self, nutrition: dict, amount: float, unit: str) -> dict:
        n = dict(nutrition)
        base = nutrition.get("base", "100g")
        if base == "piece":
            factor = amount if unit in ("piece", "dona", "ta") else amount * UNIT_TO_100G_FACTOR.get(unit, 0.1) / 1.5
        else:
            if unit in UNIT_TO_100G_FACTOR:
                factor = amount * UNIT_TO_100G_FACTOR[unit]
            elif unit in ("ml", "g"):
                factor = amount / 100
            else:
                factor = amount / 100
        factor = max(factor, 0.1)
        for key in ("calories", "protein", "fat", "carbs", "sugar", "fiber"):
            n[key] = round(n.get(key, 0) * factor, 1)
        n["calories"] = round(n.get("calories", 0))
        return n

    def _lookup_nutrition(self, food: str, amount: float, unit: str) -> Optional[dict]:
        local = self._lookup_local(food)
        if local:
            return self._scale_nutrition(local, amount, unit)
        return self._fallback_estimate(amount, unit)

    def process_text(self, text: str) -> Optional[AggregatedNutrition]:
        items = self.parser.parse(text)
        if not items:
            return None
        aggregated = AggregatedNutrition()
        for item in items:
            nutrition = self._lookup_nutrition(item.food, item.amount, item.unit)
            if nutrition:
                aggregated.add(nutrition, item.food, item.amount, item.unit)
        if not aggregated.items:
            return None
        return aggregated


