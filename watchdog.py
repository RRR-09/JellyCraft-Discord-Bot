from subprocess import Popen
from threading import Thread
from time import sleep


def run_checkscript_every_second():
  while True:
    Popen("./check")
    sleep(1)

if __name__ == '__main__':
  watchdog_thread = Thread(target=run_checkscript_every_second)
  watchdog_thread.start()
