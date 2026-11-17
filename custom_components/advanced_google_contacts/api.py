from .const import URL, FIELDS, PROFILE_URL


def _email_from_userinfo(data) -> str:
    email = (data or {}).get("email")
    if not email:
        raise ValueError("Google UserInfo response did not contain an email address")
    return str(email).strip()


async def fetch_account_email(session, access_token: str) -> str:
    """Email of the account a raw access token belongs to (used by the config flow)."""
    async with session.get(PROFILE_URL, headers={"Authorization": f"Bearer {access_token}"}) as r:
        r.raise_for_status()
        return _email_from_userinfo(await r.json())


class API:
    def __init__(self, oauth):
        self.oauth = oauth

    async def account_email(self):
        """Return the email of the Google account that owns the OAuth token."""
        r = await self.oauth.async_request("GET", PROFILE_URL)
        try:
            r.raise_for_status()
            d = await r.json()
        finally:
            r.release()
        return _email_from_userinfo(d)

    async def contacts(self):
        out = {}
        page = None
        while True:
            p = {"personFields": FIELDS, "pageSize": "1000"}
            if page:
                p["pageToken"] = page
            r = await self.oauth.async_request("GET", URL, params=p)
            try:
                r.raise_for_status()
                d = await r.json()
            finally:
                r.release()
            for person in d.get("connections", []):
                rn = person.get("resourceName")
                if not rn:
                    continue
                md = person.get("metadata") or {}
                if md.get("deleted"):
                    continue
                names = person.get("names") or []
                name = next((x.get("displayName") for x in names if x.get("displayName")), "Unbenannter Kontakt")
                clean = {k: v for k, v in person.items() if k not in ("metadata", "resourceName", "etag")}
                clean["resource_name"] = rn
                clean["display_name"] = name
                out[rn] = clean
            page = d.get("nextPageToken")
            if not page:
                return out
