import logging
import re
import ssl
from urllib.parse import urlparse

import httpx


RE_TITLE = re.compile(r"<title>([^<]+?)</title>", re.IGNORECASE)
RE_SERIAL = re.compile(r"S/N:\s*([0-9A-Za-z]+)")
RE_LOGIN = re.compile(r"\baction=login\b", re.IGNORECASE)
RE_SESSION = re.compile(r"(?:\?|&)session=(0x[0-9A-Fa-f]+)")
RE_DENIED = re.compile(r"\bAccess\s+denied\b", re.IGNORECASE)

RE_STATE = re.compile(
    r"""
    <tr\b[^>]*>                         # start table row
    (?:(?!</tr>).)*?                    # anything, not crossing end of row
    <td\b[^>]*>\s*All\s+Areas\s*</td>   # the "All Areas" cell
    \s*<td\b[^>]*>\s*([^<]+?)\s*</td>   # next cell = state text
    """,
    re.IGNORECASE | re.DOTALL | re.VERBOSE,
)

LOGGER = logging.getLogger(__name__)


def get_ssl_context():
    """
    SSL context compatible with legacy SPC panels.

    SPC typically requires:
    - TLS 1.2 only
    - invalid/self-signed cert acceptance
    - legacy RSA cipher (AES256-SHA) at lower OpenSSL security level
    - legacy renegotiation allowance (if available)
    """

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.maximum_version = ssl.TLSVersion.TLSv1_2

    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    # Legacy cipher + lower seclevel (key for OpenSSL 3.x)
    try:
        ctx.set_ciphers("AES256-SHA:@SECLEVEL=1")
    except ssl.SSLError:
        ctx.set_ciphers("DEFAULT:@SECLEVEL=1")

    opt = getattr(ssl, "OP_LEGACY_SERVER_CONNECT", None)
    if opt is not None:
        ctx.options |= opt
    else:
        LOGGER.warning("SSL lacks OP_LEGACY_SERVER_CONNECT; SPC handshake may fail")

    return ctx


def normalize_url(url, default_scheme="https"):
    """Add default scheme if missing."""
    parsed = urlparse(url)
    if not parsed.scheme:
        return f"{default_scheme}://{url}"
    return url


def parse_title(html):
    """Return [model, site] parsed from the HTML title, falling back to blanks."""
    re_match = RE_TITLE.search(html)
    if re_match:
        result = (re_match.group(1).split(" - ", 1) + [""])[:2]
    else:
        result = ("", "")
    return [s.strip() for s in result]


def parse_serial_number(html):
    """Extract the SPC serial number if present; return empty string otherwise."""
    re_match = RE_SERIAL.search(html)
    return (re_match.group(1) if re_match else "")


def parse_session_id(html):
    """Get the session token from a WebUI page or raise if missing."""
    re_match = RE_SESSION.search(html)
    if re_match:
        return re_match.group(1)
    raise ValueError("Session ID not found in HTML")


def parse_alarm_state(html):
    """Pull out the All Areas alarm state text from the system summary table."""
    re_match = RE_STATE.search(html)
    if re_match:
        return re_match.group(1).strip().lower()
    raise ValueError("Alarm state not found in HTML")


def is_login_page(html):
    return bool(RE_LOGIN.search(html))


def is_access_denied(html):
    return bool(RE_DENIED.search(html))


class SPCLoginError(Exception):
    pass


class SPCSession:
    """Async helper around the SPC WebUI session workflow and HTML parsing."""

    def __init__(self, url, userid, password):
        self._userid = userid
        self._password = password

        self.client = httpx.AsyncClient(
            base_url=normalize_url(url),
            verify=get_ssl_context(),
            timeout=httpx.Timeout(10.0),
        )

        self.creds = {
            "userid": userid,
            "password": password,
        }

        self.sid = ""
        self.model = ""
        self.serial_number = ""
        self.site = ""

    async def aclose(self):
        """Close the underlying HTTPX client."""
        await self.client.aclose()

    def _get_html(self, resp):
        """Raise for HTTP errors, parse page title metadata, and return HTML."""
        resp.raise_for_status()
        html = resp.text
        self.model, self.site = parse_title(html)
        return html

    async def _do_with_login(self, do):
        """Run a coroutine, retrying once after login if the session expired."""
        if self.sid:
            html = await do()
            if not is_login_page(html):
                return html
        await self.login()
        return await do()

    async def login(self):
        """Log in and populate session ID, serial number, model, and site."""
        url = "/login.htm?action=login&language=0"
        resp = await self.client.post(url, data=self.creds)
        html = self._get_html(resp)

        if is_login_page(html):
            if is_access_denied(html):
                raise SPCLoginError("SPC login failed: access denied")
            raise SPCLoginError("SPC login failed: still on login page")

        self.sid = parse_session_id(html)
        self.serial_number = parse_serial_number(html)

    async def get_state(self):
        """Fetch current All Areas state, handling re-login if needed."""
        async def do():
            url = f"/secure.htm?session={self.sid}&page=system_summary&language=0"
            resp = await self.client.get(url)
            return self._get_html(resp)

        html = await self._do_with_login(do)
        return parse_alarm_state(html)

    async def set_state(self, state):
        """Send an arm/disarm command and return the resulting state."""
        if state == "unset":
            data = {"unset_all_areas": "Unset"}
        elif state == "fullset":
            data = {"fullset_area1": "Fullset"}
        else:
            raise ValueError(f"{state}: unknown state")

        async def do():
            url = f"/secure.htm?session={self.sid}&page=system_summary&language=0&action=update"
            resp = await self.client.post(url, data=data)
            return self._get_html(resp)

        html = await self._do_with_login(do)
        return parse_alarm_state(html)
