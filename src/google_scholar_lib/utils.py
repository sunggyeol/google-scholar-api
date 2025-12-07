import time
import random
from fake_useragent import UserAgent

ua = UserAgent()

def get_random_user_agent():
    return ua.random

def random_sleep(min_seconds: float = 1.0, max_seconds: float = 3.0):
    time.sleep(random.uniform(min_seconds, max_seconds))

def random_sleep_long():
    time.sleep(random.uniform(5.0, 10.0))
