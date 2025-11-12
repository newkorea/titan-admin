import os
import time
import hashlib
from collections import defaultdict
import requests
from django.core.management.base import BaseCommand
from django.conf import settings

PATTERNS = [
    'error',        # generic error
    'broken pipe',  # typical client abort
    'sigpipe',      # uwsgi/network pipe issues
]

CHECK_INTERVAL = 1.0  # seconds
DEDUP_TTL = 300        # seconds suppress identical line
REOPEN_INTERVAL = 5.0  # seconds for inode check

UWSGI_LOG_PATH = os.path.join(settings.BASE_DIR, 'logs', 'uwsgi.log')

def _normalize(line: str) -> str:
    return line.strip().lower()

def _match(line: str) -> bool:
    ln = _normalize(line)
    for p in PATTERNS:
        if p in ln:
            return True
    return False

# Severity mapping for built-in patterns
SEVERITY = {
    'error': 'HIGH',
    'broken pipe': 'LOW',
    'sigpipe': 'MEDIUM',
}

# Patterns that should NOT trigger PushPlus (noise-level events)
SUPPRESS_PUSH = {
    'broken pipe',
    'sigpipe',
}

# Default per-pattern rate limits (seconds) to reduce noise
DEFAULT_RATE_LIMITS = {
    'broken pipe': int(os.environ.get('RATE_LIMIT_BROKEN_PIPE', '60')),  # one per 60s by default
}
DEFAULT_RATE_LIMIT_ALL = int(os.environ.get('RATE_LIMIT_DEFAULT', '60'))  # apply to all patterns by default

class Command(BaseCommand):
    help = 'Real-time monitor of uwsgi.log; send PushPlus notifications on error/sigpipe/broken pipe or custom patterns.'

    def add_arguments(self, parser):
        parser.add_argument('--from-start', action='store_true', help='Read from beginning instead of tail.')
        parser.add_argument('--interval', type=float, default=CHECK_INTERVAL, help='Polling interval seconds.')
        parser.add_argument('--log', type=str, default=UWSGI_LOG_PATH, help='Path to uwsgi.log.')
        parser.add_argument('--pattern', action='append', default=[], help='Additional match pattern (can repeat).')
        parser.add_argument('--exclude', action='append', default=[], help='Exclude pattern (can repeat).')
        parser.add_argument('--rate-limit-broken-pipe', type=int, default=None, help='Seconds to rate limit broken pipe alerts (default 60).')
        parser.add_argument('--rate-limit-default', type=int, default=None, help='Seconds to rate limit alerts for all patterns (default 60).')
        parser.add_argument('--once', action='store_true', help='Process current file and exit when EOF reached (test mode).')

    def handle(self, *args, **options):
        token = getattr(settings, 'PUSHPLUS_TOKEN', '') or os.environ.get('PUSHPLUS_TOKEN', '')
        if not token:
            self.stderr.write('PUSHPLUS_TOKEN not configured; exiting.')
            return

        path = options['log']
        interval = options['interval']
        from_start = options['from_start']
        once = options['once']

        # Merge patterns: built-ins + CLI + ENV
        env_extra = [p.strip().lower() for p in os.environ.get('PUSHPLUS_EXTRA_PATTERNS', '').split(',') if p.strip()]
        patterns = PATTERNS + [p.lower() for p in (options.get('pattern') or [])] + env_extra
        excludes = [p.lower() for p in (options.get('exclude') or [])]

        # Rate limits
        rate_limits = dict(DEFAULT_RATE_LIMITS)
        if options.get('rate_limit_broken_pipe') is not None:
            rate_limits['broken pipe'] = max(0, int(options['rate_limit_broken_pipe']))
        # Set default rate limit for all patterns
        rl_default = DEFAULT_RATE_LIMIT_ALL if options.get('rate_limit_default') is None else max(0, int(options['rate_limit_default']))
        for p in patterns:
            rate_limits.setdefault(p, rl_default)

        self.stdout.write(f'[monitor] Starting uwsgi log monitor: {path}')
        self.stdout.write(f'[monitor] Patterns: {patterns}')
        if excludes:
            self.stdout.write(f'[monitor] Excludes: {excludes}')
        if rate_limits:
            self.stdout.write(f'[monitor] Rate-limits: {rate_limits}')
        self.stdout.write('[monitor] PushPlus notifications enabled')

        dedup = {}  # hash -> expiry timestamp
        last_inode = None
        last_reopen_check = 0
        last_sent_by_pattern = defaultdict(lambda: 0.0)
        seen_patterns = set()  # once-only alert per pattern

        def open_log():
            nonlocal last_inode
            f = open(path, 'r', encoding='utf-8', errors='ignore')
            st = os.fstat(f.fileno())
            last_inode = st.st_ino
            if not from_start:
                f.seek(0, os.SEEK_END)
            return f

        try:
            logf = open_log()
        except FileNotFoundError:
            self.stderr.write(f'[monitor] Log file not found: {path}')
            return

        while True:
            try:
                # inode change check (rotation)
                now = time.time()
                if now - last_reopen_check >= REOPEN_INTERVAL:
                    last_reopen_check = now
                    try:
                        st = os.stat(path)
                        if st.st_ino != last_inode:
                            self.stdout.write('[monitor] Detected log rotation; reopening.')
                            logf.close()
                            logf = open_log()
                    except FileNotFoundError:
                        pass

                line = logf.readline()
                if not line:
                    if once:
                        break
                    time.sleep(interval)
                    continue

                nline = _normalize(line)

                # Exclude filters first
                if excludes and any(x in nline for x in excludes):
                    continue

                # Determine matching pattern and severity
                match = next((p for p in patterns if p in nline), None)
                if match:
                    if match in seen_patterns:
                        continue  # already alerted once for this pattern
                    h = hashlib.sha256(line.encode('utf-8')).hexdigest()
                    exp = dedup.get(h)
                    if exp and exp > time.time():
                        continue  # suppressed duplicate
                    dedup[h] = time.time() + DEDUP_TTL
                    # cleanup old hashes occasionally
                    if len(dedup) > 1000:
                        for k, v in list(dedup.items())[:500]:
                            if v < time.time():
                                dedup.pop(k, None)
                    sev = SEVERITY.get(match, 'INFO')

                    # Rate-limit certain patterns
                    rl = rate_limits.get(match)
                    now_ts = time.time()
                    if rl is not None and rl > 0:
                        last_ts = last_sent_by_pattern[match]
                        if (now_ts - last_ts) < rl:
                            # skip due to rate limit
                            continue
                        last_sent_by_pattern[match] = now_ts

                    msg = f'[{sev}] {line.strip()}'
                    # Always log locally once, but suppress PushPlus for noisy patterns
                    if match in SUPPRESS_PUSH:
                        self.stdout.write('[alert] ' + msg + ' (push suppressed)')
                    else:
                        self.stdout.write('[alert] ' + msg)
                        self._send_pushplus(token, msg, match)
                    seen_patterns.add(match)
            except KeyboardInterrupt:
                self.stdout.write('[monitor] Stopped by user')
                break
            except Exception as e:
                self.stderr.write(f'[monitor] Exception: {e}')
                time.sleep(interval)

    def _send_pushplus(self, token: str, content: str, err_type: str):
        try:
            endpoint = getattr(settings, 'PUSHPLUS_ENDPOINT', 'https://www.pushplus.plus/send')
            payload = {
                'token': token,
                'title': f'{err_type} Alert',
                'content': content,
                'template': 'txt'
            }
            resp = requests.post(endpoint, json=payload, timeout=3)
            if resp.status_code != 200:
                print('[monitor] PushPlus non-200:', resp.status_code, resp.text[:200])
        except Exception as e:
            print('[monitor] PushPlus send failed:', e)