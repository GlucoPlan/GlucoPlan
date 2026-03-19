def calculate_product_nutrition(product, weight):
    """
    Возвращает словарь с КБЖУ для заданного веса продукта.
    product: словарь из БД (ключи: calories, proteins, fats, carbs, glycemic_index)
    weight: вес в граммах
    """
    factor = weight / 100.0
    return {
        'calories': product['calories'] * factor,
        'proteins': product['proteins'] * factor,
        'fats':     product['fats'] * factor,
        'carbs':    product['carbs'] * factor,
        'gi':       product['glycemic_index'],
    }


def calculate_gn(carbs, gi):
    """Гликемическая нагрузка = (GI * carbs) / 100."""
    if gi is None or carbs == 0:
        return 0
    return (gi * carbs) / 100.0


def calculate_xe(carbs, carbs_per_xe=12):
    """Хлебные единицы."""
    if carbs_per_xe <= 0:
        return 0
    return carbs / carbs_per_xe
