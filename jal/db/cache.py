# Rules for cached database data:
# 1. A copy of source data kept for the life of the process lives in a DbCache, owned by the class that owns the table.
# 2. A writer reloads its own key with update_data(); a write that crosses classes calls JalDB.invalidate_cache().
# 3. A memo that dies with its owner (a rebuild, a model, a fetch) is a plain dict or a UniversalCache on that owner.
import inspect
from typing import Any, Callable, Hashable, Tuple

class UniversalCache:
    """
    Universal cache for functions with hashable arguments.
    
    Features:
    - Cache key: tuple (function, hashable arguments)
    - Autovalidation of arguments (must be hashable)
    - Invalidate specific cache entries (by key)
    - Guaranteed unique cache key for each function and its arguments
    """
    
    def __init__(self):
        self._cache = {}

    def get_data(
        self, 
        func: Callable, 
        args: Tuple[Hashable, ...] = ()
    ) -> Any:
        """
        Get data from cache or execute function if not cached.
        
        :param func: Function to cache/execute
        :param args: Function arguments (must be hashable)
        :return: Function result from cache or execution
        """
        key = self._create_key(func, args)
        
        if key not in self._cache:
            self._cache[key] = func(*args)
            
        return self._cache[key]

    def update_data(
            self,
            func: Callable,
            args: Tuple[Hashable, ...] = ()
    ) -> Any:
        """
        Invalidates old cache entry and executes function to have new data cached.

        :param func: Function to cache/execute
        :param args: Function arguments (must be hashable)
        :return: Function result from new execution
        """
        self.invalidate(func, args)
        return self.get_data(func, args)

    def invalidate(self, func: Callable, args: Tuple[Hashable, ...] = ()) -> None:
        """Delete a specific cache entry"""
        key = self._create_key(func, args)
        self._cache.pop(key, None)

    def clear_cache(self) -> None:
        """Clear the entire cache"""
        self._cache.clear()

    def _create_key(self, func: Callable, args: Tuple) -> Tuple:
        """Create a unique key for the cache"""
        self._validate_args_hashable(args)
        return (
            func.__module__,
            func.__name__,
            args
        )

    @staticmethod
    def _validate_args_hashable(args: Tuple) -> None:
        """Validate that all arguments are hashable"""
        try:
            hash(args)
        except TypeError:
            raise ValueError("All elements must be hashable")


class DbCache(UniversalCache):
    """A cache of database data, emptied together with all the others by clear_all()."""
    _all = []        # every DbCache of the application
    _also = []       # what else clear_all() calls: caches of database data that are kept outside a DbCache

    def __init__(self):
        super().__init__()
        DbCache._all.append(self)

    @staticmethod
    def also_clear(func: Callable) -> None:
        """Register a function for clear_all() to call"""
        DbCache._also.append(func)

    @staticmethod
    def clear_all() -> None:
        for cache in DbCache._all:
            cache.clear_cache()
        for func in DbCache._also:
            func()
