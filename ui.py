import base64
from pathlib import Path

import streamlit as st

ASSETS = Path(__file__).resolve().parent / "assets"
ICON = ASSETS / "logo_volunteer_icon.png"
LOGO = ASSETS / "logo_volunteer_full.png"

CSS = """
<style>
.block-container {padding-top: 2rem;}
.hero {
    position: relative; overflow: hidden;
    display: flex; align-items: center; gap: 20px;
    padding: 22px 28px; border-radius: 16px; margin-bottom: 18px;
    background: linear-gradient(120deg, #0E7C7B 0%, #15302E 100%); color: white;
    box-shadow: 0 8px 24px rgba(14,124,123,.25);
}
.hero::after {
    content: ""; position: absolute; right: -40px; top: -60px;
    width: 180px; height: 180px; border-radius: 50%;
    background: rgba(255,200,87,.22);
}
.hero img {
    width: 78px; height: 78px; border-radius: 50%; flex-shrink: 0;
    border: 3px solid rgba(255,244,236,.9); background: #0E7C7B;
}
.hero h1 {margin: 0; padding: 0; font-size: 1.9rem; color: white; line-height: 1.2;}
.hero p  {margin: 4px 0 0 0; opacity: .9; color: #FFF4EC;}
div[data-testid="stMetric"] {
    background: rgba(128,128,128,.08); border: 1px solid rgba(128,128,128,.25);
    border-radius: 12px; padding: 14px 16px;
}
.result-card {
    border: 1px solid rgba(46,167,122,.55); background: rgba(46,167,122,.10);
    border-radius: 12px; padding: 16px 20px; margin-top: 10px;
}
.result-card h4 {margin: 0 0 8px 0;}
.proposal-card {
    border: 1px solid rgba(128,128,128,.3); background: rgba(128,128,128,.06);
    border-radius: 12px; padding: 14px 18px; margin-bottom: 6px;
}
.pill {
    display:inline-block; padding:2px 10px; border-radius:999px;
    font-size:.8rem; font-weight:600; margin-right:6px; background: rgba(128,128,128,.18);
}
</style>
"""


def encode_image(path):
    return base64.b64encode(Path(path).read_bytes()).decode()


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def hero(title, subtitle):
    st.markdown(
        f'<div class="hero"><img src="data:image/png;base64,{encode_image(ICON)}" alt="logo">'
        f"<div><h1>{title}</h1><p>{subtitle}</p></div></div>",
        unsafe_allow_html=True,
    )


def format_minutes(minutes):
    if minutes < 60:
        return f"{minutes} min"
    hours, mins = divmod(minutes, 60)
    if hours < 24:
        return f"{hours}h {mins:02d}m"
    days, hours = divmod(hours, 24)
    return f"{days}d {hours}h"


def urgency_label(minutes):
    if minutes <= 720:
        return "🔴 Critical"
    if minutes <= 2880:
        return "🟠 Soon"
    return "🟢 Safe"
