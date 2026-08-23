import os
import signal
import sys

ESSENTIAL = {"postgres", "fastapi", "nginx"}


def parse_fields(line):
    return dict(pair.split(":", 1) for pair in line.split())


def main():
    while True:
        sys.stdout.write("READY\n")
        sys.stdout.flush()

        header = parse_fields(sys.stdin.readline())
        payload = sys.stdin.read(int(header["len"]))
        process = parse_fields(payload).get("processname", "unknown")

        if process in ESSENTIAL:
            sys.stderr.write(f"fatal_listener: essential process '{process}' died ({payload}); stopping container\n")
            sys.stderr.flush()
            sys.stdout.write("RESULT 2\nOK")
            sys.stdout.flush()
            with open("/var/run/supervisord.pid") as pidfile:
                os.kill(int(pidfile.read().strip()), signal.SIGTERM)
            return

        sys.stderr.write(f"fatal_listener: non-essential process '{process}' died ({payload}); container stays up\n")
        sys.stderr.flush()
        sys.stdout.write("RESULT 2\nOK")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
