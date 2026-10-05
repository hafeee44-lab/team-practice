import html

import streamlit as st
import streamlit.components.v1 as components

from pipeline import (
    export_inventory_to_csv,
    get_inventory_alerts,
    get_restock_recommendations,
    get_transaction_history,
    get_items,
    search_items,
)


def _inject_cursor_glow():
    """Adds a soft, cursor-reactive glow without changing app data or logic."""
    components.html(
        """
        <script>
          const documentRoot = window.parent.document.documentElement;
          window.parent.document.addEventListener('pointermove', (event) => {
            documentRoot.style.setProperty('--cursor-x', `${event.clientX}px`);
            documentRoot.style.setProperty('--cursor-y', `${event.clientY}px`);
          }, { passive: true });
        </script>
        """,
        height=0,
    )


def _toggle_theme():
    st.session_state.theme = "light" if st.session_state.theme == "dark" else "dark"


def _expiry_label(item):
    return "Expired" if item["days_left"] < 0 else f"{item['days_left']} days left"


def _styles(theme):
    is_dark = theme == "dark"
    colors = {
        "bg": "#090d18" if is_dark else "#f5f2eb",
        "surface": "rgba(19, 26, 43, 0.82)" if is_dark else "rgba(255, 255, 255, 0.78)",
        "surface_solid": "#151d31" if is_dark else "#ffffff",
        "text": "#f4f0e6" if is_dark else "#172033",
        "muted": "#a3aec4" if is_dark else "#687388",
        "line": "rgba(214, 224, 245, 0.13)" if is_dark else "rgba(23, 32, 51, 0.12)",
        "accent": "#8df7d3" if is_dark else "#127c6a",
        "accent_2": "#7d8cff" if is_dark else "#5268d6",
        "danger": "#ff8a9b" if is_dark else "#c33d55",
        "glow": "rgba(96, 128, 255, 0.20)" if is_dark else "rgba(92, 109, 255, 0.15)",
    }
    return f"""
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap');
      :root {{ --cursor-x: 50vw; --cursor-y: 30vh; }}
      html, body, [class*="css"] {{ font-family: 'Poppins', sans-serif; }}
      .stApp {{
        color: {colors['text']};
        background:
          radial-gradient(600px circle at var(--cursor-x) var(--cursor-y), {colors['glow']}, transparent 48%),
          radial-gradient(520px circle at 85% 0%, rgba(125, 140, 255, .12), transparent 44%),
          {colors['bg']};
        transition: background .25s ease;
      }}
      .block-container {{ max-width: 1180px; padding: 2.2rem 3rem 3rem; }}
      #MainMenu, footer, header {{ visibility: hidden; }}
      .hero {{ margin: .3rem 0 2.1rem; }}
      .eyebrow {{ color: {colors['accent']}; font-size: .72rem; font-weight: 700; letter-spacing: .16em; text-transform: uppercase; }}
      .hero h1 {{ color: {colors['text']}; font-size: clamp(2.2rem, 5vw, 4.45rem); line-height: .98; letter-spacing: -.07em; margin: .38rem 0 .72rem; }}
      .hero p {{ color: {colors['muted']}; max-width: 610px; font-size: 1rem; line-height: 1.75; margin: 0; }}
      .theme-wrap {{ display: flex; justify-content: flex-end; padding-top: .35rem; }}
      .st-key-theme_toggle button {{
        border: 1px solid {colors['line']}; background: {colors['surface']}; color: {colors['text']};
        border-radius: 50%; height: 2.8rem; width: 2.8rem; padding: 0; font-size: 1.1rem;
        box-shadow: 0 10px 30px rgba(0,0,0,.16); transition: transform .2s ease, border-color .2s ease;
      }}
      .st-key-theme_toggle button, .st-key-theme_toggle button p {{ background-color: {colors['surface_solid']} !important; color: {colors['text']} !important; }}
      .st-key-theme_toggle button:hover {{ transform: translateY(-2px) rotate(12deg); border-color: {colors['accent']}; }}
      .st-key-theme_toggle button:hover p {{ color: {colors['accent']} !important; }}
      .metric-card {{
        position: relative; overflow: hidden; min-height: 142px; border: 1px solid {colors['line']};
        border-radius: 20px; padding: 1.35rem 1.4rem; background: linear-gradient(135deg, {colors['surface']}, {colors['surface_solid']});
        box-shadow: 0 18px 44px rgba(0,0,0,.17), inset 0 1px rgba(255,255,255,.06);
      }}
      .metric-card::after {{ content: ''; position: absolute; width: 100px; height: 100px; border-radius: 50%; background: {colors['accent_2']}; opacity: .12; top: -48px; right: -32px; filter: blur(7px); }}
      .metric-label {{ color: {colors['muted']}; font-size: .8rem; font-weight: 600; letter-spacing: .04em; }}
      .metric-value {{ color: {colors['text']}; font-size: 2.5rem; font-weight: 700; line-height: 1.25; letter-spacing: -.06em; margin-top: .45rem; }}
      .metric-detail {{ color: {colors['accent']}; font-size: .74rem; font-weight: 600; margin-top: .35rem; }}
      .section-label {{ color: {colors['text']}; font-size: 1.1rem; font-weight: 600; margin: 2.7rem 0 1rem; }}
      .inventory {{ overflow: hidden; border: 1px solid {colors['line']}; border-radius: 20px; background: {colors['surface']}; box-shadow: 0 22px 55px rgba(0,0,0,.15); }}
      .inventory-head {{ padding: 1.25rem 1.45rem; border-bottom: 1px solid {colors['line']}; display: flex; align-items: center; justify-content: space-between; }}
      .inventory-head strong {{ color: {colors['text']}; font-size: .94rem; }}
      .inventory-head span {{ color: {colors['muted']}; font-size: .75rem; }}
      table {{ width: 100%; border-collapse: collapse; }}
      th {{ color: {colors['muted']}; background: rgba(255,255,255,.025); font-size: .69rem; font-weight: 600; letter-spacing: .09em; text-align: left; text-transform: uppercase; padding: .95rem 1.45rem; }}
      td {{ color: {colors['text']}; border-top: 1px solid {colors['line']}; font-size: .87rem; padding: 1.12rem 1.45rem; }}
      tr {{ transition: background .2s ease; }} tr:hover {{ background: rgba(125, 140, 255, .08); }}
      .medicine {{ font-weight: 600; }}
      .quantity {{ font-variant-numeric: tabular-nums; }}
      .days {{ display: inline-flex; border: 1px solid rgba(141,247,211,.23); border-radius: 999px; color: {colors['accent']}; font-size: .72rem; font-weight: 600; padding: .3rem .62rem; }}
      .filter-label {{ color: {colors['muted']}; font-size: .69rem; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; margin: 1.5rem 0 .55rem; }}
      [data-testid="stTextInput"] input, [data-testid="stSelectbox"] div[data-baseweb="select"] > div {{ background: {colors['surface_solid']} !important; border-color: {colors['line']} !important; border-radius: 12px !important; color: {colors['text']} !important; }}
      [data-testid="stTextInput"] label, [data-testid="stSelectbox"] label {{ color: {colors['muted']} !important; font-size: .72rem !important; font-weight: 600 !important; }}
      .restock-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: .85rem; }}
      .restock-card {{ border: 1px solid {colors['line']}; border-radius: 16px; padding: 1.05rem; background: {colors['surface']}; }}
      .restock-card h3 {{ color: {colors['text']}; font-size: .91rem; margin: .3rem 0 .35rem; }}
      .restock-card p {{ color: {colors['muted']}; font-size: .75rem; margin: 0; line-height: 1.65; }}
      .priority {{ color: {colors['accent']}; font-size: .65rem; font-weight: 700; letter-spacing: .1em; }}
      .section-row {{ display: flex; align-items: center; justify-content: space-between; margin: 2.7rem 0 1rem; }}
      .section-row .section-label {{ margin: 0; }}
      [data-testid="stDownloadButton"] button {{ border: 1px solid {colors['line']}; border-radius: 999px; background: {colors['surface_solid']}; color: {colors['text']}; font-size: .75rem; padding: .48rem .85rem; }}
      .audit {{ border-top: 1px solid {colors['line']}; }}
      .audit-item {{ display: grid; grid-template-columns: 1fr auto; gap: 1rem; padding: .9rem 0; border-bottom: 1px solid {colors['line']}; }}
      .audit-item strong {{ color: {colors['text']}; font-size: .8rem; }} .audit-item span {{ color: {colors['muted']}; font-size: .72rem; }}
      .empty-state {{ color: {colors['muted']}; padding: 1.5rem; text-align: center; }}
      @media (max-width: 680px) {{ .block-container {{ padding: 1.3rem 1.05rem 2rem; }} .hero h1 {{ font-size: 2.75rem; }} th, td {{ padding-left: .8rem; padding-right: .8rem; }} th:nth-child(2), td:nth-child(2) {{ display: none; }} .restock-grid {{ grid-template-columns: 1fr; }} }}
    </style>
    """


def show_dashboard():
    all_items = get_items()
    alerts = get_inventory_alerts()
    _inject_cursor_glow()
    st.markdown(_styles(st.session_state.theme), unsafe_allow_html=True)

    title, toggle = st.columns([10, 1])
    with title:
        st.markdown("""<div class="hero"><div class="eyebrow">Pharmacy intelligence / 01</div><h1>Clarity before<br>the expiry date.</h1><p>A calm operational view of your medicine inventory—built to keep essential stock visible, accountable, and ready to act on.</p></div>""", unsafe_allow_html=True)
    with toggle:
        st.markdown('<div class="theme-wrap">', unsafe_allow_html=True)
        icon = "☀" if st.session_state.theme == "dark" else "☾"
        st.button(icon, key="theme_toggle", help="Switch colour theme", on_click=_toggle_theme)
        st.markdown('</div>', unsafe_allow_html=True)

    categories = sorted({item.get("category", "General") for item in all_items})
    filters = st.columns([2, 1, 1])
    with filters[0]:
        query = st.text_input("Search inventory", placeholder="Medicine, category, or ID")
    with filters[1]:
        status_choice = st.selectbox("Expiry status", ["All statuses", "EXPIRED", "CRITICAL", "WARNING", "GOOD"])
    with filters[2]:
        category_choice = st.selectbox("Category", ["All categories", *categories])

    items = search_items(
        query=query,
        status=None if status_choice == "All statuses" else status_choice,
        category=None if category_choice == "All categories" else category_choice,
    )

    metrics = [
        ("Items tracked", alerts["total_items"], "Active catalogue"),
        ("Total packs", alerts["total_packs"], "Across all inventory"),
        ("Urgent", alerts["urgent_action_count"], "Action needed" if alerts["urgent_action_count"] else "Everything on track"),
    ]
    columns = st.columns(3)
    for column, (label, value, detail) in zip(columns, metrics):
        column.markdown(f'<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-value">{value}</div><div class="metric-detail">{detail}</div></div>', unsafe_allow_html=True)

    rows = "".join(
        f"<tr><td class='medicine'>{html.escape(item['name'])}</td><td>{html.escape(item.get('category', 'General'))}</td><td>{html.escape(item['expiry'])}</td><td class='quantity'>{item['qty']}</td><td><span class='days'>{_expiry_label(item)}</span></td></tr>"
        for item in items
    )
    if not rows:
        rows = "<tr><td class='empty-state' colspan='5'>No medicine matches these filters.</td></tr>"
    section, download = st.columns([5, 1])
    with section:
        st.markdown("<div class='section-label'>Inventory overview</div>", unsafe_allow_html=True)
    with download:
        st.markdown("<div style='height:1.8rem'></div>", unsafe_allow_html=True)
        st.download_button("Export CSV", export_inventory_to_csv(), "expirex-inventory.csv", "text/csv")
    st.markdown(
        f"""<div class="inventory"><div class="inventory-head"><strong>Medicine inventory</strong><span>LIVE STOCK POSITION</span></div><table><thead><tr><th>Medicine</th><th>Category</th><th>Expiry date</th><th>In stock</th><th>Expiry window</th></tr></thead><tbody>{rows}</tbody></table></div>""",
        unsafe_allow_html=True,
    )

    restock = get_restock_recommendations()
    st.markdown("<div class='section-label'>Restock plan</div>", unsafe_allow_html=True)
    if restock["items_to_reorder"]:
        restock_cards = "".join(
            f"<article class='restock-card'><div class='priority'>{html.escape(item['priority'])} PRIORITY</div><h3>{html.escape(item['name'])}</h3><p>Order <strong>{item['suggested_order_qty']} packs</strong> · Estimated cost ${item['estimated_cost']:.2f}</p></article>"
            for item in restock["items_to_reorder"][:3]
        )
        st.markdown(f"<div class='restock-grid'>{restock_cards}</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='empty-state'>No restocking action is currently required.</div>", unsafe_allow_html=True)

    transactions = get_transaction_history(limit=3)
    if transactions:
        audit_rows = "".join(
            f"<div class='audit-item'><div><strong>{html.escape(entry['action'].replace('_', ' ').title())}</strong> <span>· {html.escape(entry['reason'])}</span></div><span>{html.escape(entry['timestamp'])}</span></div>"
            for entry in transactions
        )
        st.markdown("<div class='section-label'>Recent activity</div><div class='audit'>" + audit_rows + "</div>", unsafe_allow_html=True)
