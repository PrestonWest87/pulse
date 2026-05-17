import streamlit as st
import pandas as pd
import time
import json
from streamlit_cookies_controller import CookieController
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from src.database import init_db
from src.collectors import get_all_collector_types
import src.services as svc

LOCAL_TZ = ZoneInfo("America/Chicago")
cookie_controller = CookieController()
st.set_page_config(page_title="Pulse — Data Collector", layout="wide")
init_db()


def safe_rerun():
    st.rerun()


# ==========================================
# AUTH
# ==========================================
if "current_user" not in st.session_state:
    st.session_state.current_user = None

if st.session_state.current_user is None:
    saved_token = cookie_controller.get("pulse_session_token")
    if saved_token:
        user = svc.get_user_by_token(saved_token)
        if user:
            st.session_state.current_user = user.username
            st.session_state.user_id = user.id

if st.session_state.current_user is None:
    st.markdown("""
    <div style='text-align:center; padding:4rem 2rem;'>
        <h1 style='font-size:3rem; margin-bottom:0;'>Pulse</h1>
        <p style='color:#888; font-size:1.1rem;'>Data Collector</p>
    </div>
    """, unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        with st.form("login"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Sign In", use_container_width=True):
                user = svc.authenticate(username, password)
                if user:
                    st.session_state.current_user = user.username
                    st.session_state.user_id = user.id
                    cookie_controller.set("pulse_session_token", user.session_token, max_age=86400 * 7)
                    safe_rerun()
                else:
                    st.error("Invalid credentials")
    st.stop()


# ==========================================
# LAYOUT
# ==========================================
st.markdown(f"""
<div style='display:flex; align-items:center; gap:12px; padding:0.5rem 0;'>
    <h1 style='margin:0; font-size:1.8rem;'>Pulse</h1>
    <span style='color:#888;'>— {st.session_state.current_user}</span>
</div>
""", unsafe_allow_html=True)

pages = ["Feed", "Sources", "Search", "Alerts", "Notifications", "Settings"]
page = st.sidebar.radio("Navigation", pages, label_visibility="collapsed")
st.sidebar.divider()
if st.sidebar.button("Sign Out", use_container_width=True):
    cookie_controller.remove("pulse_session_token")
    st.session_state.current_user = None
    safe_rerun()


def badge(status, color=""):
    colors = {"success": "#2ecc71", "error": "#e74c3c", "never": "#95a5a6",
              "info": "#3498db", "warning": "#f39c12", "critical": "#e74c3c",
              "triggered": "#e74c3c", "acknowledged": "#f39c12", "resolved": "#2ecc71"}
    c = color or colors.get(status, "#95a5a6")
    return f"<span style='display:inline-block; width:8px; height:8px; border-radius:50%; background:{c}; margin-right:4px;'></span>{status.upper()}"


# ==========================================
# FEED PAGE — all collected items
# ==========================================
if page == "Feed":
    st.subheader("Collected Data")

    col_f1, col_f2 = st.columns([2, 1])
    with col_f1:
        sources = svc.get_sources()
        src_opts = {0: "All Sources"}
        src_opts.update({s.id: s.name for s in sources})
        filter_src = st.selectbox("Source", options=list(src_opts.keys()),
                                  format_func=lambda x: src_opts[x], label_visibility="collapsed")
    with col_f2:
        total = svc.get_item_count()
        st.metric("Total Items Collected", total)

    items = svc.get_recent_items(limit=200, source_id=None if filter_src == 0 else filter_src)

    if not items:
        st.info("No data collected yet. Add a **Source** to start collecting.")
    else:
        for item in items[:100]:
            ts = svc.format_central(item.published_at) if item.published_at else svc.format_central(item.collected_at)
            st.markdown(f"""
            <div style='padding:8px 0; border-bottom:1px solid #333;'>
                <div style='display:flex; gap:8px; align-items:center;'>
                    <span style='color:#888; font-size:0.8rem; min-width:130px;'>{ts}</span>
                    <span style='font-size:0.75rem; background:#333; padding:1px 6px; border-radius:3px;'>{item.source_type}</span>
                    <span style='font-size:0.75rem; background:#444; padding:1px 6px; border-radius:3px;'>{item.source_name}</span>
                    <strong style='flex:1;'>{item.title[:120]}</strong>
                </div>
                <div style='font-size:0.85rem; color:#aaa; margin-top:2px; margin-left:130px;'>
                    {item.content[:200].strip() if item.content else ''}
                    {f'<a href="{item.url}" target="_blank" style="color:#3498db;">🔗</a>' if item.url else ''}
                </div>
            </div>
            """, unsafe_allow_html=True)

            with st.expander("View full content", expanded=False):
                st.text(item.content[:10000] if item.content else "(no content)")
                if item.raw_data:
                    st.code(json.dumps(item.raw_data, indent=2)[:2000], language="json")


# ==========================================
# SOURCES PAGE — add/manage data sources
# ==========================================
elif page == "Sources":
    tab_add, tab_list = st.tabs(["Add Source", "All Sources"])

    with tab_add:
        st.subheader("New Data Source")
        with st.form("add_source"):
            name = st.text_input("Source Name", placeholder="Hacker News, PyPI requests, etc.")
            description = st.text_area("Description (optional)", "")

            col_types = get_all_collector_types()
            type_map = {t["type_id"]: t for t in col_types}
            type_choice = st.selectbox("Collector Type", options=list(type_map.keys()),
                                       format_func=lambda x: f"{type_map[x]['name']} — {type_map[x]['description']}")

            schema = type_map[type_choice]["config_schema"]
            st.markdown("**Configuration**")
            config = {}
            for field, fcfg in schema.items():
                label = fcfg.get("label", field)
                default = fcfg.get("default", "")
                required = fcfg.get("required", False)
                enum = fcfg.get("enum", None)
                ftype = fcfg.get("type", "string")

                if enum:
                    val = st.selectbox(label, options=enum)
                elif ftype == "number":
                    val = st.number_input(label, value=int(default) if default else 0)
                elif ftype == "boolean":
                    val = st.checkbox(label, value=bool(default))
                else:
                    val = st.text_input(label, value=str(default) if default else "",
                                        placeholder="Required" if required else "")
                config[field] = val

            col_a, col_b = st.columns(2)
            with col_a:
                interval = st.number_input("Check interval (seconds)", min_value=60, value=900, step=60,
                                           help="How often to poll this source. 900s = 15min.")
            with col_b:
                alert_sev = st.selectbox("Alert severity on keyword match", ["info", "warning", "critical"], index=0)
            keywords = st.text_input("Alert on keywords (comma-separated, leave blank for no alerts)",
                                     placeholder="CVE, breach, critical, release")

            if st.form_submit_button("Create Source", use_container_width=True, type="primary"):
                if not name:
                    st.error("Name is required")
                else:
                    kw_list = [k.strip() for k in keywords.split(",") if k.strip()]
                    sid = svc.create_source(name, type_choice, config, interval, alert_sev, kw_list, description)
                    st.success(f"Source '{name}' created (ID: {sid}). Worker will pick it up within 60s.")
                    time.sleep(0.5)
                    safe_rerun()

    with tab_list:
        sources = svc.get_sources()
        if not sources:
            st.caption("No sources configured.")
        else:
            counts = {}
            for sid, sname, cnt in svc.get_source_item_counts():
                counts[sid] = cnt

            for src in sources:
                item_count = counts.get(src.id, 0)
                with st.expander(f"{src.name}  ({badge(src.last_status)}  {src.collector_type})", expanded=False):
                    col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                    with col1:
                        st.markdown(f"**Type:** {src.collector_type}  |  **Interval:** {src.interval_seconds}s")
                        cfg_show = {k: v for k, v in (src.config or {}).items()}
                        st.markdown(f"**Config:** `{json.dumps(cfg_show)[:300]}`")
                        if src.last_error:
                            st.error(src.last_error)
                        st.markdown(f"**Alert keywords:** {', '.join(src.alert_on_keywords) if src.alert_on_keywords else '(none)'}")
                    with col2:
                        st.markdown(f"{badge(src.last_status)}")
                        st.caption(f"Last: {svc.format_central(src.last_run_at) if src.last_run_at else 'never'}")
                        st.metric("Items", item_count)
                    with col3:
                        if st.button("ON/OFF", key=f"tog_{src.id}"):
                            svc.toggle_source(src.id)
                            safe_rerun()
                    with col4:
                        if st.button("Delete", key=f"del_{src.id}"):
                            svc.delete_source(src.id)
                            safe_rerun()


# ==========================================
# SEARCH PAGE — full-text across collected data
# ==========================================
elif page == "Search":
    st.subheader("Search Collected Data")

    with st.form("search_form"):
        col_s1, col_s2 = st.columns([3, 1])
        with col_s1:
            query = st.text_input("Search", placeholder="Search titles, content, URLs...", label_visibility="collapsed")
        with col_s2:
            submitted = st.form_submit_button("Search", use_container_width=True, type="primary")

    if submitted and query:
        results = svc.get_recent_items(limit=200, search=query)
        st.caption(f"{len(results)} results for '{query}'")
        if results:
            for item in results[:100]:
                ts = svc.format_central(item.published_at) if item.published_at else svc.format_central(item.collected_at)
                # Highlight matches
                title = item.title
                content = item.content[:500] if item.content else ""
                for q in query.split():
                    title = title.replace(q, f"**{q}**")
                    content = content.replace(q, f"**{q}**")
                st.markdown(f"""
                <div style='padding:6px 0; border-bottom:1px solid #333;'>
                    <span style='color:#888; font-size:0.8rem;'>{ts}</span>
                    <span style='font-size:0.75rem; background:#333; padding:1px 6px; border-radius:3px;'>{item.source_name}</span>
                    <strong>{title[:200]}</strong>
                    {f'<a href="{item.url}" target="_blank" style="color:#3498db;">🔗</a>' if item.url else ''}
                    <div style='font-size:0.85rem; color:#aaa;'>{content[:400]}</div>
                </div>
                """, unsafe_allow_html=True)
    elif not submitted:
        # Show latest items as browse
        items = svc.get_recent_items(limit=50)
        st.caption(f"Latest {len(items)} items (use search above to filter)")
        for item in items[:50]:
            ts = svc.format_central(item.published_at) if item.published_at else svc.format_central(item.collected_at)
            st.markdown(f"""
            <div style='padding:4px 0; border-bottom:1px solid #282828; font-size:0.9rem;'>
                <span style='color:#888; font-size:0.8rem;'>{ts}</span>
                <span style='color:#555;'>[{item.source_name}]</span>
                {item.title[:150]}
            </div>
            """, unsafe_allow_html=True)


# ==========================================
# ALERTS PAGE
# ==========================================
elif page == "Alerts":
    st.subheader("Alerts")

    col1, col2 = st.columns(2)
    with col1:
        f_status = st.selectbox("Status", ["All", "triggered", "acknowledged", "resolved"])
    with col2:
        f_severity = st.selectbox("Severity", ["All", "info", "warning", "critical"])

    alerts = svc.get_alerts(
        limit=200,
        status=None if f_status == "All" else f_status,
        severity=None if f_severity == "All" else f_severity,
    )

    if not alerts:
        st.info("No alerts.")
    else:
        for a in alerts[:100]:
            st.markdown(f"""
            <div style='display:flex; gap:12px; padding:6px 0; border-bottom:1px solid #333; align-items:center;'>
                <span style='color:#888; min-width:130px; font-size:0.85rem;'>{svc.format_central(a.created_at)}</span>
                <span>{badge(a.severity)}</span>
                <span>{badge(a.status)}</span>
                <strong style='flex:1;'>{a.title}</strong>
                <span style='color:#888; font-size:0.85rem;'>{a.source_name or ''}</span>
            </div>
            """, unsafe_allow_html=True)
            cols = st.columns([6, 1, 1])
            with cols[0]:
                if a.item_title:
                    st.caption(f"Item: {a.item_title} | {a.message}")
            with cols[1]:
                if a.status == "triggered":
                    if st.button("Ack", key=f"ack_{a.id}"):
                        svc.acknowledge_alert(a.id)
                        safe_rerun()
            with cols[2]:
                if a.status in ("triggered", "acknowledged"):
                    if st.button("Resolve", key=f"res_{a.id}"):
                        svc.resolve_alert(a.id)
                        safe_rerun()


# ==========================================
# NOTIFICATIONS PAGE
# ==========================================
elif page == "Notifications":
    tab_ch, tab_rules = st.tabs(["Channels", "Rules"])

    with tab_ch:
        with st.expander("Add Channel", expanded=False):
            with st.form("add_ch"):
                ch_name = st.text_input("Name")
                ch_type = st.selectbox("Type", ["webhook", "slack", "discord", "twilio_sms", "email"])
                cfg = {}
                if ch_type == "webhook":
                    cfg["url"] = st.text_input("Webhook URL")
                    cfg["method"] = st.selectbox("Method", ["POST", "PUT"])
                elif ch_type in ("slack", "discord"):
                    cfg["webhook_url"] = st.text_input("Webhook URL")
                elif ch_type == "twilio_sms":
                    cfg["account_sid"] = st.text_input("Account SID")
                    cfg["auth_token"] = st.text_input("Auth Token", type="password")
                    cfg["from_number"] = st.text_input("From")
                    cfg["to_number"] = st.text_input("To")
                elif ch_type == "email":
                    cfg["recipient"] = st.text_input("Recipient")
                if st.form_submit_button("Create", type="primary"):
                    svc.create_channel(ch_name, ch_type, cfg)
                    st.success("Channel created")
                    safe_rerun()

        for ch in svc.get_channels():
            cols = st.columns([3, 1, 1])
            with cols[0]:
                st.write(f"**{ch.name}** ({ch.channel_type})")
            with cols[1]:
                st.write("✅" if ch.enabled else "⏸")
            with cols[2]:
                if st.button("Delete", key=f"chd_{ch.id}"):
                    svc.delete_channel(ch.id)
                    safe_rerun()

    with tab_rules:
        with st.expander("Add Rule", expanded=False):
            with st.form("add_rule"):
                r_name = st.text_input("Name")
                sources = svc.get_sources()
                src_opt = {0: "All Sources"}
                src_opt.update({s.id: s.name for s in sources})
                r_src = st.selectbox("Source", options=list(src_opt.keys()), format_func=lambda x: src_opt[x])
                channels = svc.get_channels()
                ch_opt = {c.id: c.name for c in channels}
                r_ch = st.selectbox("Channel", options=list(ch_opt.keys()), format_func=lambda x: ch_opt[x]) if ch_opt else None
                r_sev = st.selectbox("Min Severity", ["info", "warning", "critical"], index=0)
                r_cool = st.number_input("Cooldown (min)", 0, 60, 5)
                if st.form_submit_button("Create", type="primary"):
                    if r_ch is None:
                        st.error("Create a channel first")
                    else:
                        svc.create_rule(r_name, None if r_src == 0 else r_src, r_ch, r_sev, r_cool)
                        st.success("Rule created")
                        safe_rerun()

        for r in svc.get_rules():
            sn = next((s.name for s in sources if s.id == r.source_id), "All") if r.source_id else "All"
            cn = next((c.name for c in channels if c.id == r.channel_id), "?") if r.channel_id else "?"
            st.markdown(f"**{r.name}** — {sn} → {cn} ({r.min_severity}, cooldown {r.cooldown_minutes}m)")
            if st.button("Delete Rule", key=f"rd_{r.id}"):
                svc.delete_rule(r.id)
                safe_rerun()


# ==========================================
# SETTINGS
# ==========================================
elif page == "Settings":
    tab_sys, tab_users = st.tabs(["System", "Users"])

    with tab_sys:
        cfg = svc.get_cached_config()
        with st.form("sys_cfg"):
            st.markdown("**SMTP**")
            c1, c2 = st.columns(2)
            with c1:
                smtp_en = st.toggle("Enable", bool(cfg.smtp_enabled))
                smtp_sv = st.text_input("Server", cfg.smtp_server or "")
                smtp_snd = st.text_input("Sender", cfg.smtp_sender or "")
            with c2:
                smtp_pt = st.number_input("Port", value=cfg.smtp_port or 587)
                smtp_us = st.text_input("Username", cfg.smtp_username or "")
                smtp_pw = st.text_input("Password", type="password", value=cfg.smtp_password or "")
            st.markdown("**LLM**")
            c3, c4 = st.columns(2)
            with c3:
                llm_ep = st.text_input("Endpoint", cfg.llm_endpoint or "", placeholder="http://localhost:11434/v1")
            with c4:
                llm_md = st.text_input("Model", cfg.llm_model_name or "gpt-3.5-turbo")
            if st.form_submit_button("Save", type="primary"):
                svc.update_config(smtp_enabled=smtp_en, smtp_server=smtp_sv, smtp_port=smtp_pt,
                                  smtp_username=smtp_us, smtp_password=smtp_pw, smtp_sender=smtp_snd,
                                  llm_endpoint=llm_ep, llm_model_name=llm_md)
                st.success("Saved")
                safe_rerun()

    with tab_users:
        with st.form("chpw"):
            pw = st.text_input("New Password", type="password")
            pw2 = st.text_input("Confirm", type="password")
            if st.form_submit_button("Update"):
                if pw and pw == pw2:
                    svc.update_user_password(st.session_state.user_id, pw)
                    st.success("Password updated")
                else:
                    st.error("Mismatch or empty")
