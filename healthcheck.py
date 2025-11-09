import sys
from urllib import request, error

def main():
    try:
        with request.urlopen('http://localhost:10000/health', timeout=5) as resp:
            code = getattr(resp, 'status', 200)
            sys.exit(0 if code == 200 else 1)
    except Exception:
        sys.exit(1)

if __name__ == '__main__':
    main()

