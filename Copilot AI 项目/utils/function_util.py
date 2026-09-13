import logging
import time


def timing_decorator(func):
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        logging.debug(f"Function {func.__name__} execution time: {end_time - start_time:.6f} seconds")
        return result

    return wrapper