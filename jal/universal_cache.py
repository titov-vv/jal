import inspect
from typing import Any, Callable, Hashable, Tuple

class UniversalCache:
    """
    Универсальный кэш для любых функций и параметров
    
    Особенности:
    - Ключ кэша: кортеж (функция, хешируемые аргументы)
    - Автоматическая проверка хешируемости аргументов
    - Поддержка инвалидации по ключу
    - Гарантированная уникальность ключей
    """
    
    def __init__(self):
        self._cache = {}

    def get_data(
        self, 
        func: Callable, 
        args: Tuple[Hashable, ...] = ()
    ) -> Any:
        """
        Получить или вычислить данные
        
        :param func: Функция для выполнения
        :param args: Аргументы для функции (должны быть хешируемыми)
        :return: Результат выполнения функции
        """
        key = self._create_key(func, args)
        
        if key not in self._cache:
            self._cache[key] = func(*args)
            
        return self._cache[key]

    def invalidate(self, func: Callable, args: Tuple[Hashable, ...] = ()) -> None:
        """Удалить запись из кэша"""
        key = self._create_key(func, args)
        self._cache.pop(key, None)

    def clear_cache(self) -> None:
        """Полностью очистить кэш"""
        self._cache.clear()

    def _create_key(self, func: Callable, args: Tuple) -> Tuple:
        """Создать уникальный ключ для кэша"""
        self._validate_args_hashable(args)
        return (
            func.__module__,
            func.__name__,
            args
        )

    @staticmethod
    def _validate_args_hashable(args: Tuple) -> None:
        """Проверить что все аргументы хешируемы"""
        try:
            hash(args)
        except TypeError:
            raise ValueError("Все элементы args должны быть хешируемыми")
