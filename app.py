import base64
import os
import random
import time
from datetime import datetime, date
import pandas as pd
import streamlit as st

from database import (
    init_db, get_connection, get_soglia_esaurimento, get_sospetto, set_sospetto,
    get_prodotti_disponibili_df, get_prodotti_tutti_df, get_lotti_attivi_df,
    get_report_lotti_integrato_df, get_movimenti_dettagliati_df, calcola_stato_magazzino
)
from game_logic import (
    inizializza_pusher_db, get_data_corrente_gioco, e_festivo_o_weekend,
    calcola_grado_reputazione, segna_debito_pagato, genera_offerta_fornitore_casuale,
    genera_cliente_in_negozio, genera_evento_casuale_giorno, esegui_transazione_vendita,
    FASCE_ORARIE, LISTA_NOMI_RAVER
)

# ==========================================
# CONFIGURAZIONE PAGINA STREAMLIT
# ==========================================
st.set_page_config(
    page_title="LaBzz - Free Party Mulino Tycoon",
    page_icon="🌲",
    layout="wide"
)

init_db()
inizializza_pusher_db()

def get_file_base64(file_path):
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode('utf-8')
    return None

def spara_fuochi_d_artificio():
    js_code = """
    <script src="https://cdn.jsdelivr.net/npm/canvas-confetti@1.6.0/dist/confetti.browser.min.js"></script>
    <script>
        var count = 200;
        var defaults = { origin: { y: 0.7 } };
        function fire(particleRatio, opts) {
          confetti(Object.assign({}, defaults, opts, {
            particleCount: Math.floor(count * particleRatio)
          }));
        }
        fire(0.25, { spread: 26, startVelocity: 55 });
        fire(0.2, { spread: 60 });
        fire(0.35, { spread: 100, decay: 0.91, scalar: 0.8 });
    </script>
    """
    st.components.v1.html(js_code, height=0)

def trigger_effetto_notte():
    js_code = """
    <div id="night-overlay" style="
        position: fixed;
        top: 0; left: 0; width: 100vw; height: 100vh;
        background: linear-gradient(180deg, #020617 0%, #090d16 50%, #1e1b4b 100%);
        backdrop-filter: blur(0px);
        z-index: 99999;
        opacity: 0;
        pointer-events: none;
        transition: opacity 1.2s ease-in-out, backdrop-filter 1.2s ease-in-out;
        display: flex;
        justify-content: center;
        align-items: center;
        color: #fbbf24;
        font-family: 'Anton', sans-serif;
        font-size: 2.5rem;
        letter-spacing: 3px;
        text-shadow: 0 0 20px rgba(251, 191, 36, 0.6);
    ">🌲 IL BOSCO SI ACCENDE... RAEV COMINCIA 🔊</div>
    <script>
        const overlay = document.getElementById('night-overlay');
        setTimeout(() => {
            overlay.style.opacity = '1';
            overlay.style.backdropFilter = 'blur(12px)';
        }, 50);
        setTimeout(() => {
            overlay.style.opacity = '0';
            overlay.style.backdropFilter = 'blur(0px)';
        }, 2200);
    </script>
    """
    st.components.v1.html(js_code, height=0)

# INITIAL STATE
if 'soldi_cassa' not in st.session_state:
    st.session_state.soldi_cassa = 200.0
if 'energia' not in st.session_state:
    st.session_state.energia = 100
if 'giorno' not in st.session_state:
    st.session_state.giorno = 1
if 'giorni_trascorsi_offset' not in st.session_state:
    st.session_state.giorni_trascorsi_offset = 0
if 'indice_fascia_oraria' not in st.session_state:
    st.session_state.indice_fascia_oraria = 0
if 'reputazione' not in st.session_state:
    st.session_state.reputazione = 15
if 'fedelta_clienti' not in st.session_state:
    st.session_state.fedelta_clienti = 10
if 'log_gioco' not in st.session_state:
    st.session_state.log_gioco = ["🌲 Benvenuto al Mulino nel Bosco! Il sound system è montato. Capitale: €200."]
if 'offerta_fornitore' not in st.session_state:
    st.session_state.offerta_fornitore = None
if 'cliente_in_negozio' not in st.session_state:
    st.session_state.cliente_in_negozio = None
if 'fornitori_visti_oggi' not in st.session_state:
    st.session_state.fornitori_visti_oggi = 0
if 'max_fornitori_oggi' not in st.session_state:
    st.session_state.max_fornitori_oggi = random.choice([0, 1, 1, 2])
if 'evento_attivo' not in st.session_state:
    st.session_state.evento_attivo = None
if 'minigioco_trattativa' not in st.session_state:
    st.session_state.minigioco_trattativa = False
if 'ultimo_report_bot' not in st.session_state:
    st.session_state.ultimo_report_bot = None
if 'recap_giornata_corrente' not in st.session_state:
    st.session_state.recap_giornata_corrente = None

if st.session_state.cliente_in_negozio is None:
    genera_cliente_in_negozio()

if st.session_state.giorno == 1 and st.session_state.offerta_fornitore is None and st.session_state.max_fornitori_oggi > 0:
    genera_offerta_fornitore_casuale()
    genera_evento_casuale_giorno()

def aggiungi_log(testo):
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.log_gioco.insert(0, f"[{timestamp}] {testo}")

def reset_completo_nuova_partita():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM movimenti;")
        cursor.execute("DELETE FROM lotti;")
        cursor.execute("DELETE FROM prodotti;")
        cursor.execute("DELETE FROM clienti;")
        cursor.execute("UPDATE pusher SET assunto = 0;")
        
        cursor.execute("INSERT INTO prodotti (nome, valore_mercato_unitario, scorta_minima_g) VALUES ('Skunk', 7.0, 20.0);")
        p_id = cursor.lastrowid
        cursor.execute("INSERT INTO lotti (prodotto_id, codice_lotto, quantita_iniziale, quantita_attuale, costo_acquisto_unitario, data_acquisto, data_carico) VALUES (?, 'MULINO-START', 50.0, 50.0, 2.50, ?, ?);", (p_id, date.today(), date.today()))
        l_id = cursor.lastrowid
        cursor.execute("INSERT INTO movimenti (prodotto_id, lotto_id, tipo, quantita, costo_totale, cliente, note) VALUES (?, ?, 'CARICO', 50.0, 125.0, 'Fornitore Furgone', 'Stock Iniziale Mulino')", (p_id, l_id))
    
    set_sospetto(10.0)
    st.session_state.soldi_cassa = 200.0
    st.session_state.giorno = 1
    st.session_state.giorni_trascorsi_offset = 0
    st.session_state.indice_fascia_oraria = 0
    st.session_state.energia = 100
    st.session_state.reputazione = 15
    st.session_state.fedelta_clienti = 10
    st.session_state.log_gioco = ["✨ Nuovo Raduno Iniziato! Il bosco risuona. Budget: €200."]
    st.session_state.offerta_fornitore = None
    st.session_state.cliente_in_negozio = None
    st.session_state.fornitori_visti_oggi = 0
    st.session_state.max_fornitori_oggi = random.choice([0, 1, 2])
    st.session_state.evento_attivo = None
    st.session_state.minigioco_trattativa = False
    st.session_state.ultimo_report_bot = None
    st.session_state.recap_giornata_corrente = None
    if st.session_state.max_fornitori_oggi > 0:
        genera_offerta_fornitore_casuale()
    genera_cliente_in_negozio()
    genera_evento_casuale_giorno()

# ==========================================
# INIEZIONE CSS CUSTOM
# ==========================================
sfondo_b64 = get_file_base64("sfondo.jpg")
bg_style = ""
if sfondo_b64:
    bg_style = f"""
    .stApp {{
        background: linear-gradient(rgba(3, 7, 18, 0.75), rgba(3, 7, 18, 0.85)), url("data:image/jpeg;base64,{sfondo_b64}") no-repeat center center fixed !important;
        background-size: cover !important;
    }}
    """
else:
    bg_style = """
    .stApp {
        background-color: #030712 !important;
        background: linear-gradient(135deg, #020617 0%, #064e3b 50%, #0f172a 100%) !important;
    }
    """

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Anton&family=Special+Elite&family=Rajdhani:wght@500;600;700&display=swap');

    {bg_style}

    header[data-testid="stHeader"] {{
        display: none !important;
    }}

    .block-container {{
        padding-top: 2rem !important;
        padding-bottom: 6rem !important;
        padding-left: 0.8rem !important;
        padding-right: 0.8rem !important;
    }}

    .logo-container {{
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        text-align: center !important;
        width: 100% !important;
        margin: 0 auto 1rem auto !important;
    }}

    .logo-container video {{
        display: block !important;
        margin: 0 auto !important;
        max-width: 380px !important;
        width: 100% !important;
        height: auto !important;
        border-radius: 8px !important;
        object-fit: contain !important;
    }}

    h1, h2, h3, h4, h5, h6 {{
        font-family: 'Anton', sans-serif !important;
        color: #facc15 !important;
        letter-spacing: 1.5px !important;
        text-transform: uppercase !important;
        text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.9);
    }}

    .top-metrics-grid {{
        display: grid !important;
        grid-template-columns: repeat(2, 1fr) !important;
        gap: 10px !important;
        width: 100% !important;
        margin-bottom: 20px !important;
    }}

    .dashboard-grid {{
        display: grid !important;
        grid-template-columns: repeat(2, 1fr) !important;
        gap: 12px !important;
        width: 100% !important;
        margin-bottom: 25px !important;
    }}

    .custom-card {{
        background: rgba(15, 23, 42, 0.88) !important;
        backdrop-filter: blur(8px) !important;
        border-left: 4px solid #10b981 !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-radius: 6px !important;
        padding: 10px 6px !important;
        display: flex !important;
        flex-direction: column !important;
        justify-content: center !important;
        align-items: center !important;
        text-align: center !important;
        width: 100% !important;
        min-height: 70px !important;
        box-shadow: 0 8px 24px rgba(0,0,0,0.7);
    }}

    .card-label {{
        color: #9ca3af !important;
        font-size: 0.62rem !important;
        font-weight: 700 !important;
        letter-spacing: 0.8px;
        text-transform: uppercase;
        margin-bottom: 2px !important;
    }}

    .card-value {{
        font-family: 'Anton', sans-serif !important;
        font-size: 1.05rem !important;
        letter-spacing: 1px;
        color: #34d399 !important;
    }}

    .stTabs [data-baseweb="tab-list"] {{
        gap: 6px !important;
        background-color: transparent !important;
        border-bottom: none !important;
        justify-content: center !important;
        flex-wrap: wrap !important;
        padding-bottom: 12px;
    }}

    .stTabs [data-baseweb="tab"] {{
        font-family: 'Anton', sans-serif !important;
        letter-spacing: 1px;
        background: rgba(15, 23, 42, 0.9) !important;
        backdrop-filter: blur(6px) !important;
        border: 1px solid rgba(255, 255, 255, 0.15) !important;
        border-radius: 4px !important;
        color: #9ca3af !important;
        font-size: 0.9rem !important;
        padding: 8px 12px !important;
    }}

    .stTabs [aria-selected="true"] {{
        background: #10b981 !important;
        color: #030712 !important;
        border-color: #10b981 !important;
    }}

    .heist-board {{
        background: rgba(15, 23, 42, 0.92);
        backdrop-filter: blur(10px);
        border: 2px dashed rgba(16, 185, 129, 0.4);
        border-radius: 8px;
        padding: 20px;
        box-shadow: 0 12px 35px rgba(0,0,0,0.9);
        margin-bottom: 20px;
        position: relative;
    }}
    .heist-title {{
        font-family: 'Anton', sans-serif;
        color: #facc15;
        font-size: 1.6rem;
        letter-spacing: 2px;
        text-transform: uppercase;
        text-align: center;
        margin-bottom: 8px;
    }}
    .heist-quote {{
        font-family: 'Special Elite', cursive;
        color: #e5e7eb;
        font-size: 0.95rem;
        text-align: center;
        background: rgba(0,0,0,0.5);
        padding: 10px;
        border-radius: 4px;
        border-left: 4px solid #10b981;
        margin-bottom: 15px;
    }}
</style>
""", unsafe_allow_html=True)

# ==========================================
# RENDER LOGO
# ==========================================
video_b64 = get_file_base64("logo.gif.mp4")
if video_b64:
    st.markdown(f"""
        <div class="logo-container">
            <video autoplay loop muted playsinline>
                <source src="data:video/mp4;base64,{video_b64}" type="video/mp4">
            </video>
        </div>
    """, unsafe_allow_html=True)
else:
    if os.path.exists("logo.png"):
        st.image("logo.png", use_container_width=True)
    else:
        st.title("Mulino Underground Tycoon")

# ==========================================
# HEADER METRICHE & HEAT METER
# ==========================================
with get_connection() as conn:
    df_lotti_scorte = pd.read_sql_query("""
        SELECT p.nome, SUM(l.quantita_attuale) as qta 
        FROM lotti l 
        JOIN prodotti p ON l.prodotto_id = p.id 
        WHERE l.quantita_attuale > 0 
        GROUP BY p.nome
    """, conn)

def get_qta_prodotto(nome_prod):
    if not df_lotti_scorte.empty and nome_prod in df_lotti_scorte['nome'].values:
        val = df_lotti_scorte[df_lotti_scorte['nome'] == nome_prod]['qta'].values[0]
        return float(val)
    return 0.0

qta_skunk = get_qta_prodotto("Skunk")
qta_hash = get_qta_prodotto("Hash Dry")
qta_lemon = get_qta_prodotto("Lemon Haze")
qta_frozen = get_qta_prodotto("Frozen Hash")

grado_rep_testo = calcola_grado_reputazione(st.session_state.reputazione)
sospetto_attuale = get_sospetto()

col_m1, col_m2 = st.columns(2)
with col_m1:
    st.markdown(f"""
    <div class="custom-card" style="margin-bottom: 8px;">
        <div class="card-label">💵 Cassa del Mulino</div>
        <div class="card-value">€ {st.session_state.soldi_cassa:,.2f}</div>
    </div>
    """, unsafe_allow_html=True)
with col_m2:
    st.markdown(f"""
    <div class="custom-card" style="margin-bottom: 8px;">
        <div class="card-label">🚨 Attenzione Forestale (Heat)</div>
        <div class="card-value">{sospetto_attuale:.1f} / 100</div>
    </div>
    """, unsafe_allow_html=True)

st.progress(int(sospetto_attuale))

st.markdown(f"""
<div class="top-metrics-grid">
    <div class="custom-card">
        <div class="card-label">📦 Scorte al Mulino</div>
        <div style="font-size: 0.60rem; font-weight: 700; margin-top: 2px; display: flex; justify-content: center; gap: 4px; flex-wrap: wrap; color: #34d399; line-height: 1.2;">
            <span>🌿 {qta_skunk:.1f}g</span> &bull; 
            <span>🧱 {qta_hash:.1f}g</span> &bull; 
            <span>🍋 {qta_lemon:.1f}g</span> &bull; 
            <span>❄️ {qta_frozen:.1f}g</span>
        </div>
    </div>
    <div class="custom-card">
        <div class="card-label">📅 Giorno nel Bosco</div>
        <div class="card-value">Giorno {st.session_state.giorno}</div>
    </div>
    <div class="custom-card">
        <div class="card-label">⚡ Energia Fisica</div>
        <div class="card-value">{st.session_state.energia}%</div>
    </div>
    <div class="custom-card">
        <div class="card-label">⭐ Rango nel Raduno</div>
        <div style="font-size: 0.75rem; font-family: 'Anton', sans-serif; color: #34d399;">{grado_rep_testo}</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ==========================================
# PULSANTE NOTTE NEL BOSCO & DATA MINIMAL
# ==========================================
data_oggi = get_data_corrente_gioco()
is_fest, desc_fest = e_festivo_o_weekend(data_oggi)
data_formattata = data_oggi.strftime("%d %B %Y")

with st.container(border=True):
    col_n1, col_n2, col_n3 = st.columns([1, 2, 1])
    with col_n2:
        if st.button("🌲 Avanza Giorno (Alba sul Fiume)", use_container_width=True):
            set_sospetto(get_sospetto() - 8.0)
            trigger_effetto_notte()
            st.session_state.giorno += 1
            st.session_state.giorni_trascorsi_offset += 1
            st.session_state.indice_fascia_oraria = 0
            st.session_state.energia = 100
            
            st.session_state.offerta_fornitore = None
            st.session_state.fornitori_visti_oggi = 0
            st.session_state.max_fornitori_oggi = random.choice([0, 1, 1, 2])
            st.session_state.minigioco_trattativa = False
            st.session_state.ultimo_report_bot = None
            st.session_state.recap_giornata_corrente = None
            
            if st.session_state.max_fornitori_oggi > 0 and random.random() < 0.60:
                genera_offerta_fornitore_casuale()
                
            genera_cliente_in_negozio()
            genera_evento_casuale_giorno()
            aggiungi_log("🌲 È sorta l'alba sul mulino. Un nuovo giorno di festa nel bosco comincia.")
            st.rerun()

    st.markdown(f"""
        <div style="text-align: center; font-family: 'Rajdhani', sans-serif; font-size: 0.78rem; font-weight: 500; color: #9ca3af; margin-top: 6px; letter-spacing: 1px;">
            {data_formattata} &bull; <span style="color: #34d399;">{desc_fest}</span>
        </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# ==========================================
# EVENTI SPECIALI NEL BOSCO
# ==========================================
if st.session_state.evento_attivo:
    ev = st.session_state.evento_attivo
    with st.container(border=True):
        st.markdown(f"### {ev['titolo']}")
        st.write(ev['testo'])
        
        if ev['tipo'] == 'polizia':
            col_ev1, col_ev2, col_ev3 = st.columns(3)
            with col_ev1:
                if st.button("💰 Corrompi Guardia Forestale (€50)", use_container_width=True):
                    if st.session_state.soldi_cassa >= 50.0:
                        st.session_state.soldi_cassa -= 50.0
                        set_sospetto(get_sospetto() - 35.0)
                        st.success("Accordo trovato lungo il fiume! La pattuglia si allontana.")
                        aggiungi_log("🌲 BOSCO: Pagata tangente alla guardia forestale di €50.")
                        st.session_state.evento_attivo = None
                        st.rerun()
                    else:
                        st.error("Fondi insufficienti per corrompere la pattuglia!")
            with col_ev2:
                if st.button("🏃 Nascondi Scorte tra gli Alberi", use_container_width=True):
                    if random.random() < (0.60 - (get_sospetto() / 200)):
                        st.success("Sei sgusciato tra i sentieri bui del bosco senza farti notare!")
                        set_sospetto(get_sospetto() - 15.0)
                    else:
                        st.warning("La forestale ha perquisito un furgone! Sequestrato materiale e scorte!")
                        st.session_state.soldi_cassa = max(0.0, st.session_state.soldi_cassa - 80.0)
                        with get_connection() as conn:
                            conn.execute("UPDATE lotti SET quantita_attuale = MAX(0.0, quantita_attuale - 10.0) WHERE quantita_attuale > 0 LIMIT 3")
                        set_sospetto(10.0)
                    st.session_state.evento_attivo = None
                    st.rerun()
            with col_ev3:
                if st.button("🔇 Abbassa i Sound System", use_container_width=True):
                    set_sospetto(get_sospetto() - 25.
