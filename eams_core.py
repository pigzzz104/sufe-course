# --- START OF FILE eams_core.py ---
import requests
import re
import json
import time
import os
import html
from urllib.parse import urlencode, quote_plus


class EamsSession:
    # 核心正则
    RE_PROFILE_ID = re.compile(r"toStdElectCourse\((\d+)\)")
    RE_H2 = re.compile(r"<h2[^>]*>(.*?)</h2>", re.IGNORECASE | re.DOTALL)
    RE_STRIP_TAGS = re.compile(r"<[^>]+>")
    RE_LESSON_JSONS = re.compile(r"lessonJSONs\s*=\s*\[(.*?)\];", re.DOTALL)
    RE_LESSON_ITEMS = re.compile(r"id:(\d+).*?no:'(.*?)'.*?name:'(.*?)'.*?code:'(.*?)'", re.DOTALL)
    RE_COUNTS_KEY = re.compile(r'(?<!")\b(\w+)\b\s*:', re.DOTALL)
    RE_TITLE = re.compile(r'<title>(.*?)</title>', re.IGNORECASE)
    RE_ALERT = re.compile(r"alert\('(.*?)'\)")
    RE_HTML_ERR = re.compile(r'font-size:1.5em">\s*(.*?)(?:</?br|</div>)', re.DOTALL | re.IGNORECASE)
    RE_DIV_CONTENT = re.compile(r"content.*?>\s*(.*?)\s*</div>", re.DOTALL)

    def __init__(self):
        self.session = requests.Session()
        self.host = "https://eams.sufe.edu.cn"
        self.profile_id = None
        self.profile_candidates = []
        self.course_db = {}
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": f"{self.host}/eams/stdElectCourse.action"
        }

    def set_user_agent(self, user_agent):
        self.headers["User-Agent"] = user_agent

    def set_cookies_from_browser(self, cookie_list):
        self.session.cookies.clear()
        for cookie in cookie_list:
            self.session.cookies.set(
                cookie.name().data().decode(),
                cookie.value().data().decode(),
                domain=cookie.domain(),
                path=cookie.path()
            )

    def _request(self, url, timeout=10, allow_redirects=True):
        """内部请求封装"""
        try:
            return self.session.get(url, headers=self.headers, timeout=timeout, allow_redirects=allow_redirects)
        except Exception as e:
            print(f"[ERROR] Core Request Failed: {e}")
            return None

    def _extract_profile_candidates(self, page_html):
        ids = self.RE_PROFILE_ID.findall(page_html or "")
        titles = []
        for raw_title in self.RE_H2.findall(page_html or ""):
            clean = self.RE_STRIP_TAGS.sub("", raw_title)
            clean = html.unescape(re.sub(r"\s+", " ", clean)).strip()
            if clean:
                titles.append(clean)

        out = []
        seen = set()
        for idx, pid in enumerate(ids):
            if pid in seen:
                continue
            seen.add(pid)
            title = titles[idx] if idx < len(titles) else f"选课入口 {idx + 1}"
            out.append({"id": pid, "title": title})
        return out

    def set_active_profile_id(self, profile_id):
        self.profile_id = str(profile_id)
        init_url = f"{self.host}/eams/stdElectCourse!defaultPage.action?electionProfile.id={self.profile_id}"
        self._request(init_url)  # 预热
        self.headers["Referer"] = init_url

    def select_profile_by_id(self, profile_id):
        profile_id = str(profile_id)
        if not self.profile_candidates:
            return False
        if profile_id not in {p["id"] for p in self.profile_candidates}:
            return False
        self.set_active_profile_id(profile_id)
        return True

    def step1_fetch_profile_id(self):
        res = self._request(f"{self.host}/eams/stdElectCourse.action")
        if not res:
            return False

        candidates = self._extract_profile_candidates(res.text)
        self.profile_candidates = candidates
        if not candidates:
            return False

        # 默认取最后一个选课入口
        self.set_active_profile_id(candidates[-1]["id"])
        return True

    def refresh_context(self):
        if not self.profile_id: return False
        url = f"{self.host}/eams/stdElectCourse!defaultPage.action?electionProfile.id={self.profile_id}"
        res = self._request(url, timeout=5, allow_redirects=False)

        if res and res.status_code == 302:
            print("[ERROR] Core: Session expired (302 Redirect).")
            return False
        if res and res.status_code == 200:
            self.headers["Referer"] = url
            return True
        return False

    def step2_fetch_course_data(self):
        if not self.profile_id: return False
        self.refresh_context()

        res = self._request(f"{self.host}/eams/stdElectCourse!data.action?profileId={self.profile_id}")
        if not res: return False

        match = self.RE_LESSON_JSONS.search(res.text)
        if match:
            items = self.RE_LESSON_ITEMS.findall(match.group(1))
            self.course_db = {_no: {"id": _id, "name": _name, "code": _code, "no": _no}
                              for _id, _no, _name, _code in items}
            return True
        return False

    def step3_query_counts(self):
        if not self.profile_id: return {}
        if "Referer" not in self.headers:
            self.headers["Referer"] = f"{self.host}/eams/stdElectCourse!defaultPage.action?electionProfile.id={self.profile_id}"

        res = self._request(f"{self.host}/eams/stdElectCourse!queryStdCount.action?profileId={self.profile_id}",
                            timeout=5)
        if not res or res.status_code != 200: return {}

        raw_json = None
        if "window.lessonId2Counts" in res.text:
            try:
                raw_json = res.text.split("window.lessonId2Counts")[1].split('=', 1)[1].strip()
                if ';' in raw_json: raw_json = raw_json.split(';')[0].strip()
            except:
                pass

        if raw_json:
            try:
                json_str = raw_json.replace("'", '"')
                json_str = self.RE_COUNTS_KEY.sub(r'"\1":', json_str)
                return json.loads(json_str)
            except:
                pass
        else:
            title_match = self.RE_TITLE.search(res.text)
            if title_match and ("登录" in title_match.group(1) or "认证" in title_match.group(1)):
                print("[ERROR] Core: Cookie expired detected.")
        return {}

    def step4_submit(self, lesson_id):
        ts = int(time.time() * 1000)
        url = (f"{self.host}/eams/stdElectCourse!batchOperator.action?"
               f"profileId={self.profile_id}&electLessonIds={lesson_id}&withdrawLessonIds=&v={ts}")

        res = self._request(url)
        if not res: return False, "网络请求失败"

        if "成功" in res.text and "失败" not in res.text:
            return True, "抢课成功"

        tip = "未知结果"
        tip_match = self.RE_ALERT.search(res.text)
        if not tip_match:
            html_match = self.RE_HTML_ERR.search(res.text)
            if html_match:
                extracted = html_match.group(1).strip()
                if any(k in extracted for k in ["失败", "冲突", "限选"]):
                    tip_match = html_match

        if not tip_match:
            tip_match = self.RE_DIV_CONTENT.search(res.text)

        if tip_match:
            tip = tip_match.group(1).strip() if isinstance(tip_match, re.Match) else str(tip_match).strip()
        else:
            tip = re.sub(r'<[^>]+>', '', res.text).strip()[:50]

        return False, re.sub(r'\s+', ' ', tip)

    def get_lesson_info_by_no(self, course_no):
        return self.course_db.get(course_no)

    def build_unified_auth_url(self, callback_service, state):
        """构造统一认证登录地址，默认可由环境变量覆盖。"""
        base = os.getenv("SUFE_UNIFIED_AUTH_URL", f"{self.host}/eams/stdElectCourse.action")
        query = urlencode({"service": callback_service, "state": state})
        connector = "&" if "?" in base else "?"
        return f"{base}{connector}{query}"

    def exchange_ticket_for_session(self, ticket, callback_service, state):
        """将回调 ticket/code 换取 requests.Session 会话。"""
        self.session.cookies.clear()

        exchange_tpl = os.getenv("SUFE_TICKET_EXCHANGE_URL", "").strip()
        if exchange_tpl:
            exchange_url = exchange_tpl.format(
                ticket=quote_plus(ticket),
                service=quote_plus(callback_service),
                state=quote_plus(state or "")
            )
            self._request(exchange_url)
        else:
            auth_url = self.build_unified_auth_url(callback_service, state)
            connector = "&" if "?" in auth_url else "?"
            self._request(f"{auth_url}{connector}ticket={quote_plus(ticket)}")

        return self.step1_fetch_profile_id()
