"""
Tai trang bai bao (co kiem tra robots.txt). Tra ve bytes de trafilatura tu nhan dang encoding.
"""

import urllib.robotparser
from urllib.parse import urlsplit

import requests


def make_session(user_agent: str) -> requests.Session:
    session = requests.Session()
    session.headers["User-Agent"] = user_agent
    return session


class Fetcher:
    def __init__(self, session, robots_agent: str, timeout: int):
        self.session = session
        self.robots_agent = robots_agent
        self.timeout = timeout
        self._robots = {}  # cache robots.txt theo tung site

    def allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        base = f"{parts.scheme}://{parts.netloc}"
        rp = self._robots.get(base)
        if rp is None:
            rp = urllib.robotparser.RobotFileParser()
            try:
                r = self.session.get(base + "/robots.txt", timeout=self.timeout)
                if r.status_code in (401, 403):
                    rp.disallow_all = True
                elif r.status_code == 200:
                    rp.parse(r.text.splitlines())
                else:
                    rp.parse([])  # khong co robots.txt -> cho phep
            except requests.RequestException:
                rp.parse([])
            self._robots[base] = rp
        return rp.can_fetch(self.robots_agent, url)

    def get(self, url: str) -> bytes | None:
        try:
            r = self.session.get(url, timeout=self.timeout)
            r.raise_for_status()
        except requests.RequestException:
            return None
        return r.content