import html
import json
import re
import time
import secrets
import hmac
import hashlib
import base64
from datetime import datetime, timezone
from urllib.parse import urlencode, urlparse, parse_qsl, urlunparse

import pandas as pd
import requests
import streamlit as st

DEFAULT_BOOKING_URL = "https://skinarin7clinic.setmore.com"
st.set_page_config(page_title="Meta Ads Studio | Skinarin7 Clinic", page_icon="📈", layout="wide")

st.markdown("""
<style>
.block-container{padding-top:1.5rem;padding-bottom:3rem;max-width:1400px}
[data-testid="stAppViewContainer"]{background:#f5f7fb}
[data-testid="stSidebar"]{background:#101828}
[data-testid="stSidebar"] *{color:#f9fafb}
.kicker{text-transform:uppercase;letter-spacing:.12em;font-size:.72rem;font-weight:800;color:#2563eb}
.hero{background:linear-gradient(120deg,#111827,#23365a 65%,#394a86);color:white;padding:1.5rem;border-radius:18px;margin-bottom:1rem}
.hero p{color:#d0d5dd;margin-bottom:0}
.metricbox{background:white;border:1px solid #e4e7ec;border-radius:14px;padding:1rem;min-height:115px}
.metriclabel{font-size:.82rem;color:#667085}
.metricvalue{font-size:1.7rem;font-weight:800;letter-spacing:-.04em;margin:.25rem 0}
.smallmuted{font-size:.78rem;color:#667085}
.panel{background:white;border:1px solid #e4e7ec;border-radius:14px;padding:1.1rem;margin:.3rem 0 1rem}
.adpreview{border:1px solid #e4e7ec;border-radius:14px;overflow:hidden;background:white;max-width:440px}
.adpreviewtop{padding:12px 14px;font-size:.85rem;font-weight:700}
.adpreviewphoto{height:150px;background:linear-gradient(135deg,#fae8ff,#e0e7ff 55%,#d1fae5);display:flex;align-items:center;justify-content:center;font-size:2.8rem}
.adpreviewtext{padding:14px;font-size:.9rem;white-space:pre-wrap}
.adpreviewbottom{border-top:1px solid #e4e7ec;background:#f9fafb;padding:12px 14px;display:flex;justify-content:space-between;gap:8px;align-items:center;font-size:.82rem}
.status{display:inline-block;padding:4px 9px;border-radius:99px;background:#fff7e6;color:#9a6700;font-weight:700;font-size:.75rem}
</style>
""", unsafe_allow_html=True)

def secret(key, default=""):
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default

def tracked_url(base_url, campaign, service, source="instagram"):
    parsed = urlparse(base_url.strip())
    if parsed.scheme != "https" or not (parsed.netloc.lower() == "setmore.com" or parsed.netloc.lower().endswith(".setmore.com")):
        raise ValueError("Nhập URL HTTPS thuộc miền setmore.com.")
    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    slug = lambda s, n: (re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:n] or "beauty_booking")
    params.update({
        "utm_source": source, "utm_medium": "paid_social",
        "utm_campaign": slug(campaign, 60), "utm_content": slug(service, 50)
    })
    return urlunparse(parsed._replace(query=urlencode(params)))

def api_version():
    v = str(secret("META_API_VERSION", "")).strip()
    return v if re.fullmatch(r"v\d+\.\d+", v) else ""

def meta_get(path, token, params=None):
    version = api_version()
    if not version:
        raise RuntimeError("Thiếu META_API_VERSION hoặc phiên bản không đúng định dạng vN.N.")
    params = dict(params or {})
    params["access_token"] = token
    response = requests.get(f"https://graph.facebook.com/{version}/{path.lstrip('/')}", params=params, timeout=25)
    try:
        data = response.json()
    except ValueError:
        data = {}
    if not response.ok or data.get("error"):
        raise RuntimeError(data.get("error", {}).get("message", f"Meta API HTTP {response.status_code}"))
    return data

def make_state():
    app_secret = str(secret("META_APP_SECRET", "")).strip()
    if not app_secret:
        raise RuntimeError("Thiếu META_APP_SECRET.")
    payload = f"{int(time.time())}:{secrets.token_urlsafe(24)}".encode()
    sig = hmac.new(app_secret.encode(), payload, hashlib.sha256).digest()
    enc = lambda b: base64.urlsafe_b64encode(b).decode().rstrip("=")
    return enc(payload) + "." + enc(sig)

def valid_state(value):
    try:
        app_secret = str(secret("META_APP_SECRET", "")).strip()
        payload_part, sig_part = value.split(".", 1)
        dec = lambda s: base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))
        payload, signature = dec(payload_part), dec(sig_part)
        expected = hmac.new(app_secret.encode(), payload, hashlib.sha256).digest()
        timestamp = int(payload.split(b":", 1)[0])
        return bool(app_secret) and hmac.compare_digest(signature, expected) and abs(time.time() - timestamp) < 600
    except Exception:
        return False

def handle_oauth_callback():
    code, state = st.query_params.get("code"), st.query_params.get("state")
    err = st.query_params.get("error_description") or st.query_params.get("error")
    if err:
        st.error(f"Meta chưa cấp quyền: {err}")
        st.query_params.clear()
        return
    if not code:
        return
    if not state or not valid_state(state):
        st.error("OAuth state không hợp lệ hoặc hết hạn. Hãy bắt đầu kết nối lại.")
        st.query_params.clear()
        return
    app_id = str(secret("META_APP_ID", "")).strip()
    app_secret = str(secret("META_APP_SECRET", "")).strip()
    redirect_uri = str(secret("META_REDIRECT_URI", "")).strip()
    version = api_version()
    if not all([app_id, app_secret, redirect_uri, version]):
        st.error("Thiếu một trong META_APP_ID, META_APP_SECRET, META_REDIRECT_URI, META_API_VERSION.")
        st.query_params.clear()
        return
    try:
        url = f"https://graph.facebook.com/{version}/oauth/access_token"
        r = requests.get(url, params={"client_id": app_id, "client_secret": app_secret, "redirect_uri": redirect_uri, "code": code}, timeout=25)
        data = r.json()
        if not r.ok or not data.get("access_token"):
            raise RuntimeError(data.get("error", {}).get("message", "Meta token exchange failed"))
        token, expires = data["access_token"], data.get("expires_in")
        try:
            lr = requests.get(url, params={"grant_type":"fb_exchange_token","client_id":app_id,"client_secret":app_secret,"fb_exchange_token":token}, timeout=25)
            ld = lr.json()
            if lr.ok and ld.get("access_token"):
                token, expires = ld["access_token"], ld.get("expires_in", expires)
        except Exception:
            pass
        st.session_state["meta_access_token"] = token
        st.session_state["meta_token_expires_in"] = expires
        st.query_params.clear()
        st.success("Meta đã kết nối trong phiên hiện tại. Token không hiển thị trên giao diện.")
        st.rerun()
    except Exception as exc:
        st.error(f"OAuth chưa hoàn tất: {exc}")
        st.query_params.clear()

with st.sidebar:
    st.markdown("## ✦ Meta Ads Studio")
    st.caption("Instagram · Beauty bookings")
    page = st.radio("WORKSPACE", ["Dashboard", "Campaign Builder", "Meta Insights", "Tracking & Setmore", "Cài đặt"], label_visibility="collapsed")
    st.divider()
    st.markdown("**Salon**")
    st.caption("Skinarin7 Clinic")
    st.markdown('<span class="status">Publishing disabled</span>', unsafe_allow_html=True)
    st.caption("MVP · draft + read-only")

handle_oauth_callback()
booking_page = str(secret("SETMORE_BOOKING_URL", DEFAULT_BOOKING_URL)).strip() or DEFAULT_BOOKING_URL
st.session_state.setdefault("campaigns", [])
st.session_state.setdefault("draft", None)
st.session_state.setdefault("tracked_page", booking_page)

if page == "Dashboard":
    st.markdown('<div class="kicker">Performance workspace</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero"><h1 style="margin:0 0 .4rem;color:white">Skinarin7 Clinic Ads</h1><p>Instagram ads → Setmore appointments. Quản lý bản nháp, link đặt lịch và tracking trong một nơi.</p></div>', unsafe_allow_html=True)
    if st.session_state.get("meta_access_token"):
        st.success("Meta đã kết nối trong phiên này.")
    else:
        st.info("Tạo bản nháp và link Setmore ngay; kết nối Meta cần cấu hình OAuth.")
    cols = st.columns(4)
    cards = [
        ("Daily budget target", "£5–10", "Ngân sách cho bản nháp"),
        ("Booking destination", "Setmore", "URL đã cấu hình"),
        ("Drafts this session", str(len(st.session_state.campaigns)), "Không lưu dài hạn"),
        ("Ad publishing", "OFF", "Không tiêu tiền quảng cáo"),
    ]
    for col, (label, value, note) in zip(cols, cards):
        col.markdown(f'<div class="metricbox"><div class="metriclabel">{label}</div><div class="metricvalue">{value}</div><div class="smallmuted">{note}</div></div>', unsafe_allow_html=True)
    st.write("")
    st.markdown('<div class="panel"><b>Workflow</b><br>1. Tạo bản nháp → 2. Gắn UTM cho Setmore → 3. Duyệt nội dung/ngân sách → 4. Đọc Meta Insights.<p class="smallmuted">Chưa có quảng cáo nào được tạo hoặc xuất bản.</p></div>', unsafe_allow_html=True)
    st.markdown("### Booking Page mặc định")
    st.code(booking_page, language=None)
    st.link_button("Mở Setmore Booking Page ↗", booking_page)
    if st.session_state.campaigns:
        st.markdown("### Drafts trong phiên hiện tại")
        st.dataframe(pd.DataFrame([{k:v for k,v in x.items() if k != "copy"} for x in st.session_state.campaigns]), use_container_width=True, hide_index=True)

elif page == "Campaign Builder":
    st.markdown('<div class="kicker">Draft · review · track</div>', unsafe_allow_html=True)
    st.title("Campaign Builder")
    st.write("Thiết kế quảng cáo Instagram dẫn thẳng đến Booking Page Setmore.")
    with st.form("campaign_form"):
        name = st.text_input("Tên chiến dịch", "Skinarin7 | New Client Bookings")
        service = st.selectbox("Dịch vụ", ["BIAB nails", "Gel manicure", "Acrylic extensions", "Pedicure", "Facial treatment", "Beauty clinic consultation", "Other"])
        objective = st.selectbox("Mục tiêu Meta dự kiến", ["Sales / website conversions", "Traffic (landing page views)", "Leads"])
        budget = st.select_slider("Ngân sách/ngày", options=[5,6,7,8,9,10], value=7, format_func=lambda x:f"£{x}")
        location = st.text_input("Khu vực phục vụ", "London, UK")
        radius = st.select_slider("Bán kính (miles)", options=[1,2,3,5,10], value=3)
        destination = st.text_input("Setmore Booking Page URL", booking_page)
        headline = st.text_input("Headline", "Book your next appointment")
        ad_copy = st.text_area("Nội dung quảng cáo", "Ready for a little self-care? Book your next appointment with Skinarin7 Clinic. Choose a service and a time that suits you online.")
        cta = st.selectbox("Call to action", ["Book Now", "Learn More", "Sign Up"])
        submit = st.form_submit_button("Tạo bản nháp & link tracking", type="primary", use_container_width=True)
    if submit:
        try:
            link = tracked_url(destination, name, service)
            st.session_state.draft = {
                "name":name.strip(),"service":service,"objective":objective,"daily_budget_gbp":float(budget),
                "location":location.strip(),"radius_miles":int(radius),"booking_url":destination.strip(),"tracked_url":link,
                "headline":headline.strip(),"copy":ad_copy.strip(),"cta":cta,
                "created_at":datetime.now(timezone.utc).isoformat(),"status":"Draft — not published"
            }
        except ValueError as exc:
            st.error(str(exc))
    draft = st.session_state.get("draft")
    if draft:
        st.divider()
        st.markdown("## Review trước khi chạy")
        left, right = st.columns([1.05,.95], gap="large")
        with left:
            st.markdown("### Cấu hình")
            st.write(f"**Tên:** {draft['name']}")
            st.write(f"**Dịch vụ:** {draft['service']} · **Mục tiêu dự kiến:** {draft['objective']}")
            st.write(f"**Ngân sách:** £{draft['daily_budget_gbp']:.2f}/ngày (ước tính £{draft['daily_budget_gbp']*30:.0f}/30 ngày nếu chạy đều)")
            st.write(f"**Khu vực:** {draft['location']} · bán kính {draft['radius_miles']} miles")
            st.markdown("**Link Setmore có UTM**")
            st.code(draft["tracked_url"], language=None)
            st.link_button("Thử mở booking page ↗", draft["tracked_url"])
            st.caption("UTM phân loại nguồn traffic; không tự chứng minh booking đã hoàn tất.")
            confirmed = st.checkbox("Tôi đã kiểm tra ngân sách, khu vực, nội dung và URL.")
            if st.button("Lưu bản duyệt cục bộ", type="primary", disabled=not confirmed, use_container_width=True):
                st.session_state.campaigns.append({**draft,"approved_at":datetime.now(timezone.utc).isoformat(),"status":"Approved locally — not published","publishing_enabled":False})
                st.success("Đã lưu bản duyệt trong phiên. Chưa có ads nào được tạo hoặc xuất bản.")
            st.download_button("Tải bản nháp JSON", json.dumps(draft,ensure_ascii=False,indent=2), "meta_ads_campaign_draft.json", "application/json")
        with right:
            st.markdown("### Preview mô phỏng")
            st.markdown(
                '<div class="adpreview"><div class="adpreviewtop">◉ &nbsp; Skinarin7 Clinic <span style="color:#667085;font-weight:400">· Sponsored</span></div>'
                '<div class="adpreviewphoto">✦ ♡ ✦</div><div class="adpreviewtext">'+html.escape(draft["copy"])+'</div>'
                '<div class="adpreviewbottom"><div><b>'+html.escape(draft["headline"])+'</b><div style="color:#667085;font-size:.75rem">skinarin7clinic.setmore.com</div></div>'
                '<b style="background:#eaf1ff;color:#2563eb;padding:7px 9px;border-radius:7px">'+html.escape(draft["cta"])+'</b></div></div>', unsafe_allow_html=True
            )
            st.warning("Đây là preview mô phỏng, không phải preview do Meta render. Publishing đang tắt.")
    if st.session_state.campaigns:
        st.markdown("### Bản nháp đã duyệt")
        df = pd.DataFrame([{k:v for k,v in x.items() if k != "copy"} for x in st.session_state.campaigns])
        st.dataframe(df,use_container_width=True,hide_index=True)
        st.download_button("Xuất drafts CSV",df.to_csv(index=False).encode("utf-8-sig"),"campaign_drafts.csv","text/csv")

elif page == "Meta Insights":
    st.markdown('<div class="kicker">Read-only integration</div>', unsafe_allow_html=True)
    st.title("Meta account & Insights")
    st.write("Luồng OAuth chính thức và endpoint chỉ đọc, tùy thuộc quyền được Meta cấp.")
    app_id = str(secret("META_APP_ID","")).strip()
    app_secret = str(secret("META_APP_SECRET","")).strip()
    redirect_uri = str(secret("META_REDIRECT_URI","")).strip()
    version = api_version()
    if not st.session_state.get("meta_access_token"):
        if not all([app_id,app_secret,redirect_uri,version]):
            st.warning("Cấu hình META_APP_ID, META_APP_SECRET, META_API_VERSION và META_REDIRECT_URI tại Streamlit Cloud → App settings → Secrets.")
        else:
            try:
                state = make_state()
                auth_url = "https://www.facebook.com/"+version+"/dialog/oauth?"+urlencode({
                    "client_id":app_id,"redirect_uri":redirect_uri,"state":state,
                    "scope":"ads_read,ads_management","response_type":"code"
                })
                st.link_button("Kết nối tài khoản Meta ↗", auth_url)
                st.caption("META_REDIRECT_URI phải khớp chính xác trong cấu hình Meta Developer.")
            except Exception as exc:
                st.error(str(exc))
    else:
        token = st.session_state["meta_access_token"]
        st.success("Meta đã kết nối trong phiên này.")
        if st.session_state.get("meta_token_expires_in"):
            st.caption(f"Thời hạn token được trả về: khoảng {int(st.session_state['meta_token_expires_in'])//3600} giờ.")
        c1,c2 = st.columns(2)
        with c1:
            if st.button("Đọc tài khoản quảng cáo",use_container_width=True):
                try:
                    result = meta_get("me/adaccounts",token,{"fields":"id,name,account_status,currency,timezone_name","limit":"100"})
                    st.session_state.meta_accounts = result.get("data",[])
                    st.success(f"Đã nhận {len(st.session_state.meta_accounts)} tài khoản từ API.")
                except Exception as exc:
                    st.error(f"Không đọc được tài khoản: {exc}")
        with c2:
            if st.button("Ngắt kết nối phiên",use_container_width=True):
                for key in ["meta_access_token","meta_token_expires_in","meta_accounts"]:
                    st.session_state.pop(key,None)
                st.rerun()
        accounts = st.session_state.get("meta_accounts",[])
        if accounts:
            choices={f"{a.get('name','Ad account')} — {a.get('id')} ({a.get('currency','')})":a.get("id") for a in accounts}
            chosen=st.selectbox("Chọn tài khoản quảng cáo",list(choices.keys()))
            if st.button("Đọc Insights 7 ngày",type="primary"):
                try:
                    result=meta_get(f"{choices[chosen]}/insights",token,{
                        "level":"campaign","date_preset":"last_7d",
                        "fields":"campaign_name,spend,impressions,reach,clicks,ctr,cpc,actions","limit":"100"
                    })
                    df=pd.DataFrame(result.get("data",[]))
                    if df.empty:
                        st.info("Không có dòng Insights trong khoảng thời gian này.")
                    else:
                        for field in ["spend","impressions","reach","clicks","ctr","cpc"]:
                            if field in df.columns: df[field]=pd.to_numeric(df[field],errors="coerce")
                        a,b,c,d=st.columns(4)
                        a.metric("Spend",f"£{df['spend'].fillna(0).sum():,.2f}" if "spend" in df else "N/A")
                        b.metric("Impressions",f"{int(df['impressions'].fillna(0).sum()):,}" if "impressions" in df else "N/A")
                        c.metric("Clicks",f"{int(df['clicks'].fillna(0).sum()):,}" if "clicks" in df else "N/A")
                        d.metric("Avg. CTR",f"{df['ctr'].mean():.2f}%" if "ctr" in df and df["ctr"].notna().any() else "N/A")
                        st.dataframe(df,use_container_width=True,hide_index=True)
                        st.download_button("Tải Insights CSV",df.to_csv(index=False).encode("utf-8-sig"),"meta_insights_last_7d.csv","text/csv")
                except Exception as exc:
                    st.error(f"Insights chưa lấy được: {exc}")
        st.caption("Token chỉ được giữ trong session này, chưa có database lưu token mã hóa lâu dài.")
    st.warning("Chưa có chức năng publish. Ứng dụng không tạo hoặc kích hoạt ads.")

elif page == "Tracking & Setmore":
    st.markdown('<div class="kicker">Booking destination</div>',unsafe_allow_html=True)
    st.title("Tracking & Setmore")
    st.write("Booking Page mặc định đã được thiết lập theo đường dẫn bạn gửi.")
    custom_url=st.text_input("Setmore Booking Page URL",st.session_state.get("tracked_page",booking_page))
    if st.button("Cập nhật URL trong phiên"):
        try:
            tracked_url(custom_url,"test","service")
            st.session_state.tracked_page=custom_url.strip()
            st.success("Đã cập nhật URL.")
        except ValueError as exc:
            st.error(str(exc))
    st.link_button("Mở Booking Page ↗",st.session_state.get("tracked_page",booking_page))
    st.markdown("### Tạo link UTM")
    with st.form("utm_form"):
        campaign=st.text_input("Tên campaign","skinarin7_november_booking")
        content=st.text_input("Dịch vụ / creative","biab_nails")
        source=st.selectbox("Nguồn",["instagram","facebook"])
        build=st.form_submit_button("Tạo link có UTM")
    if build:
        try:
            result=tracked_url(st.session_state.get("tracked_page",booking_page),campaign,content,source)
            st.code(result,language=None)
            st.link_button("Mở link đã gắn UTM ↗",result)
            st.download_button("Tải URL TXT",result,"setmore_tracked_url.txt","text/plain")
        except Exception as exc:
            st.error(str(exc))
    st.divider()
    st.markdown("### Bật Google Analytics trên Setmore")
    st.markdown("1. Tạo GA4 property và Web data stream.\n2. Sao chép Measurement ID dạng `G-XXXXXXXXXX`.\n3. Mở Setmore → **Integrations → Google Analytics**, nhập ID rồi lưu.\n4. Kiểm tra Realtime/events sau khi có traffic.\n\nUTM phân loại nguồn; hãy đối chiếu lịch hẹn thực tế để xác minh booking.")
    st.link_button("Hướng dẫn Setmore chính thức ↗","https://support.setmore.com/en/articles/490934-connect-setmore-with-google-analytics")

else:
    st.markdown('<div class="kicker">Configuration & safety</div>',unsafe_allow_html=True)
    st.title("Cài đặt")
    st.markdown("### URL Setmore")
    st.code(f'SETMORE_BOOKING_URL = "{booking_page}"',language="toml")
    secrets_example = (
        'SETMORE_BOOKING_URL = "https://skinarin7clinic.setmore.com"\n'
        'META_APP_ID = "your_meta_app_id"\n'
        'META_APP_SECRET = "your_meta_app_secret"\n'
        'META_API_VERSION = "vXX.X" # thay bằng phiên bản API đang được hỗ trợ\n'
        'META_REDIRECT_URI = "https://YOUR-APP.streamlit.app/"'
    )
    st.markdown("### Secrets cần đặt trong Streamlit Cloud")
    st.code(secrets_example,language="toml")
    st.warning("Không commit secrets.toml, Meta token, app secret hoặc mật khẩu vào GitHub.")
    st.markdown("### Trạng thái MVP")
    st.markdown("- **Dùng ngay:** Campaign Builder, preview mô phỏng, link Setmore có UTM, tải draft JSON/CSV.\n- **Sau cấu hình Meta OAuth:** thử đọc tài khoản quảng cáo và Insights, tùy quyền/API version.\n- **Chưa có:** tạo/publish ads, lưu token/draft lâu dài, nhiều người dùng hoặc xác nhận booking conversion theo từng quảng cáo.")
    st.info("Giới hạn £5–10 chỉ áp dụng cho bản nháp; publishing đang tắt nên đây chưa phải giới hạn chi tiêu thực tế.")

st.caption("Meta Ads Studio MVP · Draft + read-only integration · Publishing disabled")
