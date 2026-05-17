import streamlit as st
import pandas as pd
import time
import uuid
import json
from streamlit_cookies_controller import CookieController
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import streamlit.components.v1 as components

import src.services as svc
from src.database import init_db
from src.monitors import get_all_monitor_types

LOCAL_TZ = ZoneInfo("America/Chicago")
cookie_controller = CookieController()

st.set_page_config(page_title="Pulse — Universal Monitor", layout="wide")

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
            st.session_state.role = user.role

if st.session_state.current_user is None:
    st.markdown("""
    <div style='text-align:center; padding:4rem 2rem;'>
        <h1 style='font-size:3rem; margin-bottom:0;'>Pulse</h1>
        <p style='color:#888; font-size:1.1rem;'>Universal Monitor & Alerting Platform</p>
    </div>
    """, unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        with st.form("login"):
            username = st.text_input("Username", placeholder="admin")
            password = st.text_input("Password", type="password", placeholder="admin123")
            if st.form_submit_button("Sign In", use_container_width=True):
                user = svc.authenticate(username, password)
                if user:
                    st.session_state.current_user = user.username
                    st.session_state.user_id = user.id
                    st.session_state.role = user.role
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

pages = ["Dashboard", "Monitors", "Alerts", "Notifications", "Settings"]
page = st.sidebar.radio("Navigation", pages, label_visibility="collapsed")

st.sidebar.divider()

if st.sidebar.button("Sign Out", use_container_width=True):
    cookie_controller.remove("pulse_session_token")
    st.session_state.current_user = None
    safe_rerun()

# ==========================================
# HELPERS
# ==========================================

def status_badge(status):
    colors = {
        "up": "#2ecc71", "down": "#e74c3c", "degraded": "#f39c12",
        "error": "#e74c3c", "never": "#95a5a6", "triggered": "#e74c3c",
        "acknowledged": "#f39c12", "resolved": "#2ecc71", "suppressed": "#95a5a6"
    }
    c = colors.get(status, "#95a5a6")
    return f"<span style='display:inline-block; width:10px; height:10px; border-radius:50%; background:{c}; margin-right:4px;'></span>{status.upper()}"


# ==========================================
# DASHBOARD PAGE
# ==========================================

if page == "Dashboard":
    st.subheader("Monitor Status")

    monitors = svc.get_monitors()
    if not monitors:
        st.info("No monitors configured yet. Go to **Monitors** to add one.")
    else:
        cols = st.columns(3)
        for i, m in enumerate(monitors):
            with cols[i % 3]:
                st.markdown(f"""
                <div style='border:1px solid #444; border-radius:8px; padding:1rem; margin-bottom:1rem; 
                            background: {'#1a3a1a' if m.last_status == 'up' else '#3a1a1a' if m.last_status in ('down','error') else '#3a3a1a' if m.last_status == 'degraded' else '#1a1a1a'}'>
                    <div style='display:flex; justify-content:space-between; align-items:center;'>
                        <strong>{m.name}</strong>
                        {status_badge(m.last_status)}
                    </div>
                    <div style='font-size:0.85rem; color:#888; margin-top:4px;'>{m.monitor_type}</div>
                    <div style='font-size:0.85rem; color:#aaa; margin-top:4px;'>
                        {'Last: ' + svc.format_central(m.last_check_at) if m.last_check_at else 'Never checked'}
                    </div>
                    <div style='font-size:0.85rem; color:#aaa;'>
                        {'Response: ' + str(round(m.last_response_time_ms, 0)) + 'ms' if m.last_response_time_ms else ''}
                    </div>
                    {f"<div style='font-size:0.85rem; color:#e74c3c; margin-top:2px;'>{m.last_error[:100]}</div>" if m.last_error else ""}
                    <div style='margin-top:8px; display:flex; gap:4px;'>
                        <span style='font-size:0.75rem; background:#333; padding:2px 8px; border-radius:4px;'>{'ON' if m.enabled else 'OFF'}</span>
                        <span style='font-size:0.75rem; background:#333; padding:2px 8px; border-radius:4px;'>Every {m.interval_seconds}s</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

    st.divider()
    st.subheader("Recent Alerts")
    alerts = svc.get_alerts(limit=20)
    if alerts:
        for a in alerts[:10]:
            st.markdown(f"""
            <div style='display:flex; gap:12px; padding:6px 0; border-bottom:1px solid #333; font-size:0.9rem;'>
                <span style='color:#888; min-width:140px;'>{svc.format_central(a.created_at)}</span>
                <span>{status_badge(a.severity)}</span>
                <strong>{a.title}</strong>
                <span style='color:#888;'>{a.monitor_name}</span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.caption("No alerts yet")


# ==========================================
# MONITORS PAGE
# ==========================================

elif page == "Monitors":
    tab_add, tab_list = st.tabs(["Add Monitor", "All Monitors"])

    with tab_add:
        st.subheader("Create New Monitor")
        with st.form("add_monitor"):
            name = st.text_input("Monitor Name", placeholder="My Website")
            description = st.text_area("Description (optional)", "")
            mon_types = get_all_monitor_types()
            type_map = {t["type_id"]: t for t in mon_types}
            type_choice = st.selectbox("Monitor Type", options=list(type_map.keys()),
                                       format_func=lambda x: f"{type_map[x]['name']} — {type_map[x]['description']}")

            schema = type_map[type_choice]["config_schema"]
            st.markdown("**Configuration**")
            config = {}
            for field, fcfg in schema.items():
                ftype = fcfg.get("type", "string")
                label = fcfg.get("label", field)
                default = fcfg.get("default", "")
                required = fcfg.get("required", False)
                enum = fcfg.get("enum", None)

                if enum:
                    val = st.selectbox(label, options=enum, index=0)
                elif ftype == "number":
                    val = st.number_input(label, value=default, format="%d" if isinstance(default, int) else "%f")
                elif ftype == "string":
                    val = st.text_input(label, value=str(default) if default else "",
                                        placeholder="Required" if required else "")
                else:
                    val = st.text_input(label, value=str(default) if default else "")
                config[field] = val

            col_a, col_b, col_c = st.columns(3)
            with col_a:
                interval = st.number_input("Check Interval (seconds)", min_value=10, value=300, step=30)
            with col_b:
                severity = st.selectbox("Alert Severity", options=["info", "warning", "critical"], index=1)
            with col_c:
                alert_on = st.multiselect("Alert On", options=["down", "degraded", "error"], default=["down", "error"])

            if st.form_submit_button("Create Monitor", use_container_width=True, type="primary"):
                if not name:
                    st.error("Name is required")
                else:
                    mid = svc.create_monitor(name, type_choice, config, interval, severity, alert_on, description)
                    st.success(f"Monitor '{name}' created (ID: {mid})")
                    time.sleep(0.5)
                    safe_rerun()

    with tab_list:
        monitors = svc.get_monitors()
        if not monitors:
            st.caption("No monitors configured yet.")
        else:
            for m in monitors:
                with st.expander(f"{m.name}  ({status_badge(m.last_status)}  {m.monitor_type})"):
                    col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                    with col1:
                        st.markdown(f"**Type:** {m.monitor_type}  |  **Interval:** {m.interval_seconds}s  |  **Severity:** {m.severity}")
                        st.markdown(f"**Config:** `{json.dumps(m.config, indent=2)[:300]}`")
                        if m.last_error:
                            st.error(m.last_error)
                    with col2:
                        st.markdown(f"**Status:** {m.last_status.upper() if m.last_status else 'NEVER'}")
                        st.caption(f"Last: {svc.format_central(m.last_check_at) if m.last_check_at else '—'}")
                    with col3:
                        if st.button("Toggle ON/OFF", key=f"tog_{m.id}"):
                            svc.toggle_monitor(m.id)
                            safe_rerun()
                    with col4:
                        if st.button("Delete", key=f"del_{m.id}"):
                            svc.delete_monitor(m.id)
                            safe_rerun()

                    # Show recent checks
                    checks = svc.get_monitor_checks(m.id, 10)
                    if checks:
                        st.markdown("**Recent Checks**")
                        df = pd.DataFrame([
                            {"Time": svc.format_central(c.checked_at), "Status": c.status.upper(),
                             "Response (ms)": round(c.response_time_ms, 0) if c.response_time_ms else "",
                             "Summary": (c.response_summary or "")[:80],
                             "Error": (c.error or "")[:80]}
                            for c in checks
                        ])
                        st.dataframe(df, hide_index=True, use_container_width=True, height=min(200, 35 * len(df) + 35))


# ==========================================
# ALERTS PAGE
# ==========================================

elif page == "Alerts":
    st.subheader("Alert History")

    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        filter_status = st.selectbox("Status", options=["All", "triggered", "acknowledged", "resolved", "suppressed"])
    with col_f2:
        filter_severity = st.selectbox("Severity", options=["All", "info", "warning", "critical"])
    with col_f3:
        monitors = svc.get_monitors()
        mon_map = {0: "All"}
        mon_map.update({m.id: m.name for m in monitors})
        filter_monitor = st.selectbox("Monitor", options=list(mon_map.keys()),
                                      format_func=lambda x: mon_map[x])

    alerts = svc.get_alerts(
        limit=200,
        status=None if filter_status == "All" else filter_status,
        severity=None if filter_severity == "All" else filter_severity,
        monitor_id=None if filter_monitor == 0 else filter_monitor,
    )

    if not alerts:
        st.info("No alerts matching your filters.")
    else:
        for a in alerts[:100]:
            st.markdown(f"""
            <div style='display:flex; gap:12px; padding:8px 0; border-bottom:1px solid #333; align-items:center;'>
                <span style='color:#888; min-width:140px; font-size:0.85rem;'>{svc.format_central(a.created_at)}</span>
                <span>{status_badge(a.severity)}</span>
                <span>{status_badge(a.status)}</span>
                <strong style='flex:1;'>{a.title}</strong>
                <span style='color:#888; font-size:0.85rem;'>{a.monitor_name or ''}</span>
            </div>
            """, unsafe_allow_html=True)

            cols = st.columns([6, 1, 1, 1])
            with cols[0]:
                if a.message:
                    st.caption(f"Message: {a.message}")
            with cols[1]:
                if a.status == "triggered":
                    if st.button("Acknowledge", key=f"ack_{a.id}"):
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
    tab_channels, tab_rules = st.tabs(["Notification Channels", "Notification Rules"])

    with tab_channels:
        st.subheader("Channels")
        with st.expander("Add Channel", expanded=False):
            with st.form("add_channel"):
                ch_name = st.text_input("Channel Name", placeholder="My Slack")
                ch_type = st.selectbox("Type", options=["webhook", "slack", "discord", "twilio_sms", "email"])
                st.markdown("**Configuration**")
                ch_config = {}
                if ch_type == "webhook":
                    ch_config["url"] = st.text_input("Webhook URL")
                    ch_config["method"] = st.selectbox("Method", options=["POST", "PUT"], index=0)
                elif ch_type == "slack":
                    ch_config["webhook_url"] = st.text_input("Slack Incoming Webhook URL")
                    ch_config["channel"] = st.text_input("Channel (optional)", placeholder="#alerts")
                elif ch_type == "discord":
                    ch_config["webhook_url"] = st.text_input("Discord Webhook URL")
                elif ch_type == "twilio_sms":
                    ch_config["account_sid"] = st.text_input("Twilio Account SID")
                    ch_config["auth_token"] = st.text_input("Twilio Auth Token", type="password")
                    ch_config["from_number"] = st.text_input("From Number", placeholder="+15551234567")
                    ch_config["to_number"] = st.text_input("To Number", placeholder="+15559876543")
                elif ch_type == "email":
                    ch_config["recipient"] = st.text_input("Recipient Email")

                if st.form_submit_button("Create Channel", type="primary"):
                    cid = svc.create_channel(ch_name, ch_type, ch_config)
                    st.success(f"Channel '{ch_name}' created")
                    safe_rerun()

        channels = svc.get_channels()
        if channels:
            for ch in channels:
                with st.container():
                    cols = st.columns([3, 1, 1, 1])
                    with cols[0]:
                        st.write(f"**{ch.name}** ({ch.channel_type})")
                        show = {k: ("***" if "token" in k or "password" in k or "key" in k else v)
                                for k, v in (ch.config or {}).items()}
                        st.caption(f"Config: {json.dumps(show)[:200]}")
                    with cols[1]:
                        st.write(f"{'✅ Enabled' if ch.enabled else '⏸ Disabled'}")
                    with cols[2]:
                        if st.button("Toggle", key=f"cht_{ch.id}"):
                            svc.update_channel(ch.id, enabled=not ch.enabled)
                            safe_rerun()
                    with cols[3]:
                        if st.button("Delete", key=f"chd_{ch.id}"):
                            svc.delete_channel(ch.id)
                            safe_rerun()
        else:
            st.caption("No channels configured. Add one above.")

    with tab_rules:
        st.subheader("Rules")
        with st.expander("Add Rule", expanded=False):
            with st.form("add_rule"):
                r_name = st.text_input("Rule Name", placeholder="Alert admin on failure")
                monitors = svc.get_monitors()
                mon_opts = {0: "All Monitors (global rule)"}
                mon_opts.update({m.id: m.name for m in monitors})
                r_mon = st.selectbox("Monitor", options=list(mon_opts.keys()),
                                     format_func=lambda x: mon_opts[x])
                channels = svc.get_channels()
                ch_opts = {c.id: c.name for c in channels}
                r_ch = st.selectbox("Channel", options=list(ch_opts.keys()),
                                    format_func=lambda x: ch_opts[x]) if ch_opts else None
                r_sev = st.selectbox("Min Severity", options=["info", "warning", "critical"], index=1)
                r_cool = st.number_input("Cooldown (minutes)", min_value=0, value=5)

                if st.form_submit_button("Create Rule", type="primary"):
                    if r_ch is None:
                        st.error("Create a channel first")
                    else:
                        rid = svc.create_rule(r_name, None if r_mon == 0 else r_mon, r_ch, r_sev, r_cool)
                        st.success(f"Rule '{r_name}' created")
                        safe_rerun()

        rules = svc.get_rules()
        if rules:
            for r in rules:
                mon_name = next((m.name for m in monitors if m.id == r.monitor_id), "All") if r.monitor_id else "All"
                ch_name = next((c.name for c in channels if c.id == r.channel_id), "?") if r.channel_id else "?"
                st.markdown(f"""
                <div style='display:flex; gap:12px; padding:6px 0; border-bottom:1px solid #333; align-items:center;'>
                    <strong>{r.name}</strong>
                    <span style='color:#888;'>Monitor: {mon_name}</span>
                    <span style='color:#888;'>Channel: {ch_name}</span>
                    <span style='color:#888;'>Severity: {r.min_severity}</span>
                    <span style='color:#888;'>Cooldown: {r.cooldown_minutes}m</span>
                    <span style='color:#2ecc71;'>{'ON' if r.enabled else 'OFF'}</span>
                </div>
                """, unsafe_allow_html=True)
                if st.button("Delete Rule", key=f"rd_{r.id}"):
                    svc.delete_rule(r.id)
                    safe_rerun()
        else:
            st.caption("No rules configured. Add one above.")


# ==========================================
# SETTINGS PAGE
# ==========================================

elif page == "Settings":
    tab_sys, tab_users = st.tabs(["System Config", "Users"])

    with tab_sys:
        st.subheader("System Configuration")
        config = svc.get_cached_config()

        with st.form("sys_config"):
            st.markdown("**SMTP**")
            c1, c2 = st.columns(2)
            with c1:
                smtp_enabled = st.toggle("Enable SMTP", value=bool(config.smtp_enabled))
                smtp_server = st.text_input("SMTP Server", value=config.smtp_server or "")
                smtp_sender = st.text_input("Sender Email", value=config.smtp_sender or "")
            with c2:
                smtp_port = st.number_input("SMTP Port", value=config.smtp_port or 587)
                smtp_username = st.text_input("SMTP Username", value=config.smtp_username or "")
                smtp_password = st.text_input("SMTP Password", type="password", value=config.smtp_password or "")

            st.markdown("**LLM** (for AI summaries)")
            c3, c4 = st.columns(2)
            with c3:
                llm_endpoint = st.text_input("LLM Endpoint", value=config.llm_endpoint or "", placeholder="http://localhost:11434/v1")
                llm_model = st.text_input("Model Name", value=config.llm_model_name or "gpt-3.5-turbo")
            with c4:
                llm_key = st.text_input("API Key (optional)", type="password", value=config.llm_api_key or "")

            if st.form_submit_button("Save Settings", type="primary"):
                svc.update_config(
                    smtp_enabled=smtp_enabled, smtp_server=smtp_server, smtp_port=smtp_port,
                    smtp_username=smtp_username, smtp_password=smtp_password, smtp_sender=smtp_sender,
                    llm_endpoint=llm_endpoint, llm_api_key=llm_key or config.llm_api_key,
                    llm_model_name=llm_model,
                )
                st.success("Settings saved")
                safe_rerun()

    with tab_users:
        st.subheader("User Management")
        with st.form("change_password"):
            st.markdown("**Change Password**")
            new_pw = st.text_input("New Password", type="password")
            confirm_pw = st.text_input("Confirm", type="password")
            if st.form_submit_button("Update Password"):
                if new_pw and new_pw == confirm_pw:
                    svc.update_user_password(st.session_state.user_id, new_pw)
                    st.success("Password updated")
                else:
                    st.error("Passwords do not match or are empty")
