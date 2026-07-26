import random

def spin_roulette():
    return random.randint(0, 36)

def get_color(number):
    if number == 0:
        return 'зеленый'
    reds = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]
    return 'красный' if number in reds else 'черный'

def get_parity(number):
    if number == 0:
        return 'ноль'
    return 'чет' if number % 2 == 0 else 'нечет'