import time

from genesis import task


@task
def demo_sleep(seconds: int) -> str:
    time.sleep(seconds)
    return f"slept {seconds}s"
