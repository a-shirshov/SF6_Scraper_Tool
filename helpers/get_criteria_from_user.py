def get_criteria_from_user():
    """Запрашивает у пользователя критерии для проверки игроков. Пользователь может пропустить любое поле."""
    try:
        min_matches = input("Введите минимальное количество раундов (x) или оставьте пустым для пропуска: ")
        max_matches = input("Введите максимальное количество раундов (y) или оставьте пустым для пропуска: ")
        max_rating = input("Введите максимально допустимое кол-во очков (например, 19000) или оставьте пустым для пропуска: ")
        
        min_matches = int(min_matches) if min_matches else None
        max_matches = int(max_matches) if max_matches else None
        max_rating =  int(max_rating) if max_rating else None
        
        return min_matches, max_matches, max_rating
    except ValueError:
        print("Ошибка ввода. Убедитесь, что вы вводите числовые значения для количества матчей.")
        return None, None, None
